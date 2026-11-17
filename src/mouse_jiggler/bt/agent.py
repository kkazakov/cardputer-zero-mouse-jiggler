"""BlueZ pairing agent that accepts "Just Works" pairing.

Bluetooth LE/BR-EDR pairing needs a registered agent to answer the SSP
callbacks. A mouse has no display and no keypad for a PIN, so we register with
capability ``NoInputNoOutput`` and accept everything.

The agent needs a D-Bus main loop to receive method calls. dbus-python's GLib
integration runs in a daemon thread; :func:`start_mainloop` must be called
*before* ``dbus.SystemBus()`` is created.
"""

from __future__ import annotations

import logging
import threading

log = logging.getLogger(__name__)

AGENT_PATH = "/org/bluez/mousejiggler/agent"
AGENT_IFACE = "org.bluez.Agent1"

try:  # pragma: no cover - import guard for machines without dbus-python
    import dbus
    import dbus.service

    _DBUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    dbus = None  # type: ignore[assignment]
    _DBUS_AVAILABLE = False

_mainloop = None
_mainloop_thread: threading.Thread | None = None
_mainloop_lock = threading.Lock()


def start_mainloop():
    """Start the GLib loop used by dbus-python. Idempotent."""
    global _mainloop, _mainloop_thread
    with _mainloop_lock:
        if _mainloop is not None:
            return _mainloop
        from dbus.mainloop.glib import DBusGMainLoop
        from gi.repository import GLib

        DBusGMainLoop(set_as_default=True)
        _mainloop = GLib.MainLoop()
        _mainloop_thread = threading.Thread(target=_mainloop.run, name="dbus-glib", daemon=True)
        _mainloop_thread.start()
        log.debug("GLib D-Bus main loop started")
        return _mainloop


def stop_mainloop() -> None:
    global _mainloop
    with _mainloop_lock:
        if _mainloop is not None and _mainloop.is_running():
            _mainloop.quit()
        _mainloop = None


if _DBUS_AVAILABLE:

    class PairingAgent(dbus.service.Object):  # type: ignore[misc]
        def __init__(self, bus) -> None:
            super().__init__(bus, AGENT_PATH)
            self._bus = bus
            self._registered = False

        # -- registration --------------------------------------------------
        def register(self) -> None:
            manager = dbus.Interface(
                self._bus.get_object("org.bluez", "/org/bluez"), "org.bluez.AgentManager1"
            )
            try:
                manager.RegisterAgent(AGENT_PATH, "NoInputNoOutput")
            except dbus.DBusException as exc:
                if exc.get_dbus_name() != "org.bluez.Error.AlreadyExists":
                    raise
                manager.UnregisterAgent(AGENT_PATH)
                manager.RegisterAgent(AGENT_PATH, "NoInputNoOutput")
            manager.RequestDefaultAgent(AGENT_PATH)
            self._registered = True
            log.info("pairing agent registered (NoInputNoOutput)")

        def unregister(self) -> None:
            if not self._registered:
                return
            try:
                manager = dbus.Interface(
                    self._bus.get_object("org.bluez", "/org/bluez"), "org.bluez.AgentManager1"
                )
                manager.UnregisterAgent(AGENT_PATH)
            except Exception as exc:  # pragma: no cover - shutdown path
                log.debug("agent unregister failed: %s", exc)
            self._registered = False
            try:
                self.remove_from_connection()
            except Exception:
                pass

        # -- org.bluez.Agent1 ---------------------------------------------
        @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
        def Release(self) -> None:
            log.debug("agent released by bluez")

        @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="s")
        def RequestPinCode(self, device: str) -> str:
            log.info("pairing %s with PIN 0000", device)
            return "0000"

        @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
        def DisplayPinCode(self, device: str, pincode: str) -> None:
            log.info("pairing %s: PIN %s", device, pincode)

        @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="u")
        def RequestPasskey(self, device: str):
            log.info("pairing %s with passkey 0", device)
            return dbus.UInt32(0)

        @dbus.service.method(AGENT_IFACE, in_signature="ouq", out_signature="")
        def DisplayPasskey(self, device: str, passkey, entered) -> None:
            log.info("pairing %s: passkey %06d", device, int(passkey))

        @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
        def RequestConfirmation(self, device: str, passkey) -> None:
            log.info("pairing %s confirmed (passkey %06d)", device, int(passkey))

        @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="")
        def RequestAuthorization(self, device: str) -> None:
            log.info("pairing %s authorised", device)

        @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
        def AuthorizeService(self, device: str, uuid: str) -> None:
            log.info("service %s authorised for %s", uuid, device)

        @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
        def Cancel(self) -> None:
            log.info("pairing cancelled by host")

else:  # pragma: no cover

    class PairingAgent:  # type: ignore[no-redef]
        def __init__(self, *_args, **_kwargs) -> None:
            raise RuntimeError("python3-dbus is not installed")

        def register(self) -> None:
            raise RuntimeError("python3-dbus is not installed")

        def unregister(self) -> None:
            pass
