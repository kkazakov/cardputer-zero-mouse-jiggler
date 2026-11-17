"""Application core: state machine, timers, key handling and rendering.

The app is a plain object with an explicit ``step()``. It does not own threads,
sleep or read the clock directly — that makes the whole state machine testable
with a fake clock, a fake transport and a fake display.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from PIL import Image

from .config import Config
from .hid.motion import MotionEngine
from .input import keypad as keys
from .input.text import EditAction, NameEditor
from .modes import MODES
from .state import State
from .ui import screens
from .ui.theme import CAROUSEL

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .bt.transport import Transport

log = logging.getLogger(__name__)

START_INDEX = CAROUSEL.index("start")
PAIR_INDEX = CAROUSEL.index("pair")
MODE_INDEX = CAROUSEL.index("mode")


class App:
    draw_interval = 0.05    # min gap between state-driven redraws
    tick_interval = 1.0     # refresh timers once per second

    def __init__(
        self,
        transport: Transport,
        display,
        keypad,
        config: Config,
        *,
        clock: Callable[[], float] = time.monotonic,
        pairing_seconds: float = 180.0,
    ) -> None:
        self.transport = transport
        self.display = display
        self.keypad = keypad
        self.config = config
        self.clock = clock
        self.pairing_seconds = pairing_seconds

        self.state = State.OFFLINE
        self.selected = START_INDEX if config.last_host else PAIR_INDEX
        self.mode = config.mode % len(MODES)
        self.motion = MotionEngine(self.mode)
        self.editor = NameEditor()
        self.error: tuple[str, str] = ("", "")

        self.reports = 0
        self.moved = 0
        self.run_started = 0.0
        self.next_tick = 0.0
        self.pair_deadline = 0.0

        self._dirty = True
        self._last_draw = float("-inf")
        self._stop = False
        self._started = False
        self._closed = False

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> bool:
        try:
            self.transport.start()
        except Exception as exc:
            reason = str(exc) or exc.__class__.__name__
            log.error("Bluetooth unavailable: %s", reason)
            self.error = (reason, "Check bluetoothd and run as root")
            self.state = State.ERROR
            self._dirty = True
            return False
        self._started = True
        self.state = State.OFFLINE
        self._dirty = True
        log.info("Bluetooth ready")
        return True

    def run(self) -> None:
        if not self._started and not self.start():
            self._draw(self.clock())
            return
        try:
            while not self._stop:
                self.step()
        finally:
            self.shutdown()

    def stop(self) -> None:
        self._stop = True

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self.state is State.RUNNING:
                self.transport.send_mouse(0, 0)
            self.transport.close()
        except Exception as exc:  # pragma: no cover - best effort
            log.warning("shutdown: %s", exc)

    # -- one iteration -----------------------------------------------------
    def step(self) -> None:
        now = self.clock()

        for event in self.keypad.poll() if self.keypad else ():
            self.on_key(event, now)

        self.transport.poll(0.02)
        self._sync(now)
        self._tick(now)
        self._maybe_draw(now)

    # -- input -------------------------------------------------------------
    def on_key(self, event: keys.KeyEvent, now: float | None = None) -> None:
        now = self.clock() if now is None else now
        if self.state is State.RENAME and self._rename_key(event, now):
            return
        if event.pressed:
            if event.code == keys.KEY_ESC:
                return
            action = keys.NAMES.get(event.code)
            if action == "prev":
                self._select(-1)
            elif action == "next":
                self._select(1)
            elif action == "ok":
                self._activate(now)
            return

        if event.code == keys.KEY_ESC:
            self._escape()
            self._dirty = True

    def _select(self, delta: int) -> None:
        self.selected = (self.selected + delta) % len(CAROUSEL)
        self._dirty = True

    def _escape(self) -> None:
        if self.state is State.PAIRING:
            self.transport.stop_pairing()
            self.state = State.OFFLINE
        elif self.state is State.CONFIRM:
            self.state = State.CONNECTED if self.transport.connected else State.OFFLINE
        elif self.state is State.RENAME:
            self.state = State.CONNECTED if self.transport.connected else State.OFFLINE
        elif self.state in (State.OFFLINE, State.CONNECTED, State.RUNNING):
            # A single ESC leaves the app from the main screen.
            self.stop()
        elif self.state is State.ERROR:
            self.stop()

    def _activate(self, now: float) -> None:
        if self.state is State.ERROR:
            self._retry()
            return

        if self.state is State.CONFIRM:
            self.transport.unpair()
            self.transport.drop_host()
            self.transport.stop_pairing()
            self._begin_pairing(now)
            return

        if self.state is State.PAIRING:
            return

        item = CAROUSEL[self.selected]

        if item == "rename":
            self._begin_rename()

        elif item == "pair":
            if self.transport.connected:
                self.state = State.CONFIRM
                self._dirty = True
            else:
                self._begin_pairing(now)

        elif item == "start":
            if self.state is State.RUNNING:
                self._stop_motion()
            elif self.transport.connected:
                self._begin_motion(now)
            else:
                self._begin_pairing(now)

        elif item == "mode":
            self._cycle_mode(now)

    def _begin_rename(self) -> None:
        self.editor.reset(self.config.device_name, select_all=True)
        self.state = State.RENAME
        self._dirty = True
        log.info("renaming device (current: %s)", self.config.device_name)

    def _rename_key(self, event: keys.KeyEvent, now: float) -> bool:
        """Handle a key press while the name editor is open.

        Returns True when the event is consumed; ESC release must fall through
        so the global short/hold escape handling still works.
        """
        if event.code == keys.KEY_ESC:
            return bool(event.pressed)

        action = self.editor.handle(event)
        if action is EditAction.SUBMIT:
            self._save_name()
        elif action is EditAction.CHANGED:
            self._dirty = True
        return True

    def _save_name(self) -> None:
        name = self.editor.commit()
        if not name:
            self._dirty = True
            return
        self.config.device_name = name
        self.config.save()
        try:
            self.transport.rename(name)
        except Exception as exc:  # BlueZ may reject the SDP swap while connected
            log.warning("could not apply the new name now: %s", exc)
        self.state = State.CONNECTED if self.transport.connected else State.OFFLINE
        self._dirty = True
        log.info("device name set to %s", name)

    def _cycle_mode(self, now: float) -> None:
        self.mode = (self.mode + 1) % len(MODES)
        self.motion.set_mode(self.mode)
        if self.state is State.RUNNING:
            self.next_tick = now + self.motion.period
        self.config.mode = self.mode
        self.config.save()
        self._dirty = True
        log.info("mode: %s", MODES[self.mode].label)

    # -- transitions -------------------------------------------------------
    def _begin_pairing(self, now: float) -> None:
        try:
            self.transport.start_pairing(int(self.pairing_seconds))
        except Exception as exc:
            log.error("cannot start pairing: %s", exc)
            self._fail(str(exc) or "cannot enable pairing mode")
            return
        self.state = State.PAIRING
        self.pair_deadline = now + self.pairing_seconds
        self.selected = PAIR_INDEX
        self._dirty = True
        log.info("pairing window open for %ss", int(self.pairing_seconds))

    def _begin_motion(self, now: float) -> None:
        self.state = State.RUNNING
        self.run_started = now
        self.reports = 0
        self.moved = 0
        self.motion.reset()
        self.next_tick = now + self.motion.period
        self._dirty = True
        log.info("running: %s", MODES[self.mode].label)

    def _stop_motion(self) -> None:
        if self.state is not State.RUNNING:
            return
        self.state = State.CONNECTED
        self.transport.send_mouse(0, 0)
        self._dirty = True
        log.info("stopped after %d reports", self.reports)

    def _retry(self) -> None:
        log.info("retrying Bluetooth setup")
        try:
            self.transport.close()
        except Exception:
            pass
        self.start()

    def _fail(self, reason: str) -> None:
        self.error = (reason, "")
        self.state = State.ERROR
        self._dirty = True

    # -- periodic work -----------------------------------------------------
    def _sync(self, now: float) -> None:
        connected = self.transport.connected

        if connected and self.state is State.PAIRING:
            self.transport.stop_pairing()
            self.state = State.CONNECTED
            self.selected = START_INDEX
            self._remember_host()
            self._dirty = True
            log.info("host connected: %s", self.transport.host_name)

        if connected and self.state is State.OFFLINE:
            self.state = State.CONNECTED
            self.selected = START_INDEX
            self._remember_host()
            self._dirty = True

        if not connected and self.state is State.CONFIRM:
            self.state = State.OFFLINE
            self._dirty = True

        if not connected and self.state in (State.CONNECTED, State.RUNNING):
            if self.state is State.RUNNING:
                self._stop_motion()
            self.state = State.OFFLINE
            self._dirty = True
            log.info("host disconnected")

        if self.state is State.PAIRING and now >= self.pair_deadline:
            self.transport.stop_pairing()
            self.state = State.OFFLINE
            self._dirty = True
            log.info("pairing window expired")

    def _remember_host(self) -> None:
        address = getattr(self.transport, "host_address", "") or ""
        if address and address != self.config.last_host:
            self.config.last_host = address
            self.config.save()

    def _tick(self, now: float) -> None:
        if self.state is not State.RUNNING:
            return
        if now < self.next_tick:
            return

        dx, dy = self.motion.next_vector()
        if self.transport.send_mouse(dx, dy):
            self.reports += 1
            self.moved += abs(dx) + abs(dy)

        self.next_tick += self.motion.period
        if self.next_tick <= now:  # suspended / stalled: skip, do not burst
            self.next_tick = now + self.motion.period

    # -- rendering ---------------------------------------------------------
    def _maybe_draw(self, now: float) -> None:
        if self._dirty and now - self._last_draw >= self.draw_interval:
            self._draw(now)
            return
        tick_due = now - self._last_draw >= self.tick_interval
        if self.state in (State.RUNNING, State.PAIRING) and tick_due:
            self._draw(now)
            return
        if self.state is State.RENAME and now - self._last_draw >= 0.4:
            self._draw(now)

    def _draw(self, now: float) -> None:
        image = self.render(now)
        try:
            self.display.show(image)
        except Exception as exc:  # pragma: no cover - display failure is fatal-ish
            log.error("display error: %s", exc)
        self._last_draw = now
        self._dirty = False

    def render(self, now: float) -> Image.Image:
        if self.state is State.ERROR:
            return screens.render_error(self.error[0], self.error[1])
        if self.state is State.PAIRING:
            remaining = max(0, int(round(self.pair_deadline - now)))
            return screens.render_pairing(remaining)
        if self.state is State.CONFIRM:
            host = self.transport.host_name or "this host"
            return screens.render_confirm(host)
        if self.state is State.RENAME:
            return screens.render_rename(
                self.editor.text,
                cursor=int(now * 2) % 2 == 0,
                connected=self.transport.connected,
            )
        return screens.render_home(
            screens.HomeState(
                selected=self.selected,
                running=self.state is State.RUNNING,
                mode=self.mode,
                elapsed=self.elapsed(now),
                reports=self.reports,
                paired=self.transport.connected,
                device_name=self.config.device_name,
            )
        )

    def elapsed(self, now: float) -> str:
        if self.state is not State.RUNNING:
            return "00:00:00"
        total = max(0, int(now - self.run_started))
        hours, rest = divmod(total, 3600)
        minutes, seconds = divmod(rest, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
