"""The Bluetooth transport used by the app: profile + agent + HIDP server.

The app only sees this small interface: start, poll, send mouse reports,
pairing window, connected state. Tests substitute a fake with the same shape.
"""

from __future__ import annotations

import logging
from typing import Protocol

from ..constants import DEFAULT_DEVICE_NAME
from . import agent as agent_module
from .profile import BluezError, BluezProfile
from .server import HidServer, HidServerError

log = logging.getLogger(__name__)


class TransportError(RuntimeError):
    """Anything that stops the Bluetooth side from working."""


class Transport(Protocol):
    def start(self) -> None: ...
    def poll(self, timeout: float = 0.0) -> None: ...
    def send_mouse(self, dx: int = 0, dy: int = 0, buttons: int = 0, wheel: int = 0) -> int: ...
    def start_pairing(self, seconds: int = 180) -> None: ...
    def stop_pairing(self) -> None: ...
    def unpair(self) -> None: ...
    def rename(self, name: str) -> None: ...
    def drop_host(self) -> None: ...
    def close(self) -> None: ...

    @property
    def connected(self) -> bool: ...
    @property
    def host_name(self) -> str: ...
    @property
    def host_address(self) -> str: ...


class BluetoothTransport:
    def __init__(self, adapter: str = "hci0", device_name: str = DEFAULT_DEVICE_NAME) -> None:
        self.adapter = adapter
        self.device_name = device_name
        self.profile: BluezProfile | None = None
        self.server: HidServer | None = None
        self.agent = None
        self._pairing = False

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        try:
            try:
                agent_module.start_mainloop()
            except Exception as exc:  # gi/dbus missing: pairing may still work
                log.warning("D-Bus main loop unavailable (%s); pairing agent disabled", exc)

            self.profile = BluezProfile(self.adapter, name=self.device_name)
            self.profile.open()
            self.profile.configure()

            self.server = HidServer()
            self.server.start(self.profile.address)

            self.profile.register_profile()

            try:
                self.agent = agent_module.PairingAgent(self.profile.bus)
                self.agent.register()
            except Exception as exc:
                log.warning("pairing agent not registered: %s", exc)
                self.agent = None
        except (BluezError, HidServerError) as exc:
            self.close()
            raise TransportError(str(exc)) from exc
        except Exception as exc:  # pragma: no cover - unexpected stack failure
            self.close()
            raise TransportError(f"Bluetooth setup failed: {exc}") from exc

    def close(self) -> None:
        if self._pairing and self.profile is not None:
            try:
                self.profile.set_pairing(False)
            except Exception:
                pass
        self._pairing = False
        if self.agent is not None:
            try:
                self.agent.unregister()
            except Exception:
                pass
            self.agent = None
        if self.server is not None:
            self.server.close()
            self.server = None
        if self.profile is not None:
            self.profile.close()
            self.profile = None

    # -- runtime -----------------------------------------------------------
    def poll(self, timeout: float = 0.0) -> None:
        if self.server is not None:
            self.server.poll(timeout)

    def send_mouse(self, dx: int = 0, dy: int = 0, buttons: int = 0, wheel: int = 0) -> int:
        if self.server is None:
            return 0
        return self.server.send_mouse(dx, dy, buttons, wheel)

    def start_pairing(self, seconds: int = 180) -> None:
        if self.profile is None:
            raise TransportError("Bluetooth is not initialised")
        try:
            self.profile.set_pairing(True, seconds)
        except BluezError as exc:
            raise TransportError(f"cannot enable pairing mode: {exc}") from exc
        self._pairing = True

    def stop_pairing(self) -> None:
        if self.profile is None or not self._pairing:
            return
        try:
            self.profile.set_pairing(False)
        except BluezError as exc:  # keep the UI responsive even if BlueZ is unhappy
            log.warning("could not disable pairing mode: %s", exc)
        self._pairing = False

    def unpair(self) -> None:
        if self.profile is None:
            return
        address = self.host_address
        if address:
            self.profile.forget(address)

    def rename(self, name: str) -> None:
        self.device_name = name
        if self.profile is not None:
            try:
                self.profile.rename(name)
            except BluezError as exc:
                raise TransportError(f"cannot rename device: {exc}") from exc

    def drop_host(self) -> None:
        if self.server is not None:
            self.server.drop_host()

    @property
    def connected(self) -> bool:
        return bool(self.server and self.server.connected)

    @property
    def host_address(self) -> str:
        return self.server.host_address if self.server else ""

    @property
    def host_name(self) -> str:
        if self.profile is None or not self.host_address:
            return ""
        return self.profile.device_name(self.host_address)
