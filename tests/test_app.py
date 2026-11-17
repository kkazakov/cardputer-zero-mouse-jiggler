"""State machine tests driven by a fake clock and transport."""

from __future__ import annotations

import pytest
from support import FakeClock, FakeDisplay, FakeTransport, ScriptedKeypad

from mouse_jiggler.app import App
from mouse_jiggler.config import Config
from mouse_jiggler.input.keypad import (
    KEY_C,
    KEY_ENTER,
    KEY_ESC,
    KEY_Z,
    KeyEvent,
)
from mouse_jiggler.state import State
from mouse_jiggler.ui.theme import CAROUSEL


@pytest.fixture
def env(tmp_path):
    transport = FakeTransport()
    display = FakeDisplay()
    keypad = ScriptedKeypad()
    clock = FakeClock()
    config = Config(path=tmp_path / "config.json")
    app = App(transport, display, keypad, config, clock=clock,
              pairing_seconds=180.0)
    assert app.start()
    return app, transport, display, keypad, clock, config


def press(app, code, now=None):
    app.on_key(KeyEvent(code, True), now)
    app.on_key(KeyEvent(code, False), now)


def test_starts_offline_and_offers_pairing(env):
    app, transport, *_ = env
    assert transport.started
    assert app.state is State.OFFLINE
    assert app.selected == 0  # no saved host yet -> Pair is centred


def test_failed_bluetooth_shows_error(tmp_path):
    transport = FakeTransport()
    transport.fail_start = "adapter hci0 is not available"
    app = App(transport, FakeDisplay(), ScriptedKeypad(), Config(path=tmp_path / "c.json"),
              clock=FakeClock())
    assert app.start() is False
    assert app.state is State.ERROR
    assert "adapter" in app.error[0]


def test_pair_then_host_connects(env):
    app, transport, _, _, clock, config = env
    press(app, KEY_ENTER)  # activate Pair
    assert app.state is State.PAIRING
    assert transport.pairing_calls == ["start:180"]

    transport.connect()
    app.step()
    assert app.state is State.CONNECTED
    assert transport.pairing_calls[-1] == "stop"
    assert app.selected == 1  # Start is centred after connecting
    assert config.last_host == transport.host_address


def test_pairing_failure_shows_error(env):
    app, transport, _, _, clock, _ = env
    def boom(*_args, **_kwargs):
        raise RuntimeError("bluez says no")

    transport.start_pairing = boom
    press(app, KEY_ENTER)
    assert app.state is State.ERROR
    assert "bluez" in app.error[0]


def test_pairing_timeout_closes_window(env):
    app, transport, _, _, clock, _ = env
    press(app, KEY_ENTER)
    clock.advance(180)
    app.step()
    assert app.state is State.OFFLINE
    assert transport.pairing_calls[-1] == "stop"


def test_start_stop_and_zero_report(env):
    app, transport, _, _, clock, _ = env
    transport.connect()
    app.step()
    assert app.state is State.CONNECTED

    press(app, KEY_ENTER)
    assert app.state is State.RUNNING
    assert transport.reports == []

    clock.advance(30)
    app.step()
    assert transport.reports == [(2, 0)]
    assert app.reports == 1
    assert app.moved == 2

    clock.advance(30)
    app.step()
    assert transport.reports == [(2, 0), (-2, 0)]
    assert app.elapsed(clock.now) == "00:01:00"

    press(app, KEY_ENTER)
    assert app.state is State.CONNECTED
    assert transport.reports[-1] == (0, 0)


def test_mode_cycles_and_persists(env):
    app, transport, _, _, clock, config = env
    app.selected = 2  # Mode
    press(app, KEY_ENTER)
    assert app.mode == 1
    assert config.mode == 1
    assert config.path.exists()

    press(app, KEY_ENTER)
    press(app, KEY_ENTER)
    assert app.mode == 0


def test_link_loss_stops_motion(env):
    app, transport, _, _, clock, _ = env
    transport.connect()
    app.step()
    press(app, KEY_ENTER)
    clock.advance(30)
    app.step()
    assert app.reports == 1

    transport.disconnect()
    app.step()
    assert app.state is State.OFFLINE
    clock.advance(60)
    app.step()
    assert app.reports == 1  # nothing sent after the link dropped


def test_short_escape_cancels_pairing(env):
    app, transport, _, _, clock, _ = env
    press(app, KEY_ENTER)
    assert app.state is State.PAIRING

    app.on_key(KeyEvent(KEY_ESC, True), clock.now)
    app.on_key(KeyEvent(KEY_ESC, False), clock.now + 0.4)
    app.step()
    assert app.state is State.OFFLINE
    assert transport.pairing_calls[-1] == "stop"


def test_single_escape_exits_from_home(env):
    app, transport, _, _, clock, _ = env
    press(app, KEY_ESC, clock.now)
    assert app._stop is True


def test_single_escape_stops_motion_before_exit(env):
    app, transport, _, _, clock, _ = env
    transport.connect()
    app.step()
    press(app, KEY_ENTER)
    clock.advance(30)
    app.step()
    assert app.state is State.RUNNING

    press(app, KEY_ESC, clock.now)
    assert app._stop is True
    app.shutdown()
    assert transport.reports[-1] == (0, 0)


def test_escape_in_rename_only_leaves_the_editor(env):
    app, transport, _, _, clock, _ = env
    transport.connect()
    app.step()
    app.selected = CAROUSEL.index("rename")
    press(app, KEY_ENTER)
    assert app.state is State.RENAME

    press(app, KEY_ESC, clock.now)
    assert app.state is State.CONNECTED
    assert app._stop is False


def test_repair_flow(env):
    app, transport, _, _, clock, _ = env
    transport.connect()
    app.step()
    app.selected = 0  # Pair
    press(app, KEY_ENTER)
    assert app.state is State.CONFIRM

    press(app, KEY_ENTER)
    assert transport.unpaired == 1
    assert app.state is State.PAIRING


def test_confirm_page_falls_back_when_host_leaves(env):
    app, transport, _, _, clock, _ = env
    transport.connect()
    app.step()
    app.selected = 0  # Pair
    press(app, KEY_ENTER)
    assert app.state is State.CONFIRM

    transport.disconnect()
    app.step()
    assert app.state is State.OFFLINE


def test_keys_flow_through_keypad(env):
    app, transport, _, keypad, clock, _ = env
    app.selected = 1
    keypad.queue(KeyEvent(KEY_C, True), KeyEvent(KEY_C, False))
    app.step()
    assert app.selected == 2  # start -> mode

    keypad.queue(KeyEvent(KEY_Z, True), KeyEvent(KEY_Z, False))
    app.step()
    assert app.selected == 1


def test_render_produces_panel_sized_images(env):
    app, transport, _, _, clock, _ = env
    assert app.render(clock.now).size == (320, 170)

    app.on_key(KeyEvent(KEY_ENTER, True), clock.now)
    assert app.state is State.PAIRING
    assert app.render(clock.now).size == (320, 170)

    transport.connect()
    app.step()
    assert app.render(clock.now).size == (320, 170)
