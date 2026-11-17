"""Thin BlueZ D-Bus wrapper: adapter properties and the HID profile.

Errors are normalised to :class:`BluezError` with a message that can be shown
on the device's error page. Nothing here touches L2CAP sockets — that is
bt/server.py's job.
"""

from __future__ import annotations

import logging

from ..bt.sdp import make_sdp_record
from ..constants import DEFAULT_DEVICE_NAME

log = logging.getLogger(__name__)

BLUEZ = "org.bluez"
HID_UUID = "00001124-0000-1000-8000-00805F9B34FB"
PROFILE_PATH = "/org/bluez/mousejiggler"
MOUSE_CLASS = 0x000580  # peripheral / pointing device


class BluezError(RuntimeError):
    """Bluetooth stack unavailable, or a D-Bus call was rejected."""


class BluezProfile:
    def __init__(self, adapter: str = "hci0", name: str = DEFAULT_DEVICE_NAME,
                 profile_path: str = PROFILE_PATH) -> None:
        self.adapter = adapter
        self.name = name
        self.profile_path = profile_path
        self._bus = None
        self._registered = False
        self._device_names: dict[str, str] = {}

    # -- lifecycle ---------------------------------------------------------
    def open(self) -> None:
        try:
            import dbus
        except ImportError as exc:  # pragma: no cover - device dependency
            raise BluezError("python3-dbus is not installed") from exc

        try:
            self._bus = dbus.SystemBus()
            self._props().Get("org.bluez.Adapter1", "Address")
        except Exception as exc:  # dbus.exceptions.DBusException and friends
            raise BluezError(f"Bluetooth adapter {self.adapter} is not available") from exc

        log.info("using adapter %s (%s)", self.adapter, self.address)

    @property
    def bus(self):
        if self._bus is None:
            raise BluezError("D-Bus is not open")
        return self._bus

    @property
    def address(self) -> str:
        return str(self._props().Get("org.bluez.Adapter1", "Address"))

    def configure(self) -> None:
        """Power the radio, name it, and make it look like a mouse."""
        self._set("Powered", True)
        self._set("Alias", self.name)
        # A previous crash may have left the radio discoverable; start clean.
        for key in ("Pairable", "Discoverable"):
            try:
                self._set(key, False)
            except BluezError as exc:
                log.debug("adapter property %s not settable: %s", key, exc)
        for key, value in (("Class", MOUSE_CLASS), ("DiscoverableTimeout", 180)):
            try:
                self._set(key, value)
            except BluezError as exc:  # cosmetic / optional on some stacks
                log.debug("adapter property %s not settable: %s", key, exc)

    # -- HID profile -------------------------------------------------------
    def register_profile(self) -> None:
        manager = self._manager()
        try:  # a previous crash may have left the record behind
            manager.UnregisterProfile(self.profile_path)
        except Exception:
            pass
        try:
            manager.RegisterProfile(
                self.profile_path,
                HID_UUID,
                {
                    "ServiceRecord": make_sdp_record(self.name),
                    "Role": "server",
                    "RequireAuthentication": True,
                    "RequireAuthorization": False,
                },
            )
        except Exception as exc:
            raise BluezError(f"BlueZ rejected the HID profile: {_reason(exc)}") from exc
        self._registered = True
        log.info("HID profile registered at %s", self.profile_path)

    def rename(self, name: str) -> None:
        """Change the adapter alias and re-register the SDP record."""
        self.name = name
        self._set("Alias", name)
        if self._registered:
            self.unregister_profile()
            self.register_profile()
        log.info("device renamed to %s", name)

    def unregister_profile(self) -> None:
        if not self._registered:
            return
        try:
            self._manager().UnregisterProfile(self.profile_path)
        except Exception as exc:  # pragma: no cover - shutdown path
            log.debug("UnregisterProfile failed: %s", _reason(exc))
        self._registered = False

    # -- pairing -----------------------------------------------------------
    def set_pairing(self, enabled: bool, timeout: int = 180) -> None:
        if enabled:
            try:
                self._set("DiscoverableTimeout", timeout)
            except BluezError:
                pass
        self._set("Pairable", enabled)
        self._set("Discoverable", enabled)
        log.info("pairing mode %s", "on" if enabled else "off")

    def forget(self, address: str) -> None:
        path = f"/org/bluez/{self.adapter}/dev_{address.upper().replace(':', '_')}"
        try:
            adapter = self._adapter()
            adapter.RemoveDevice(path)
        except Exception as exc:
            log.warning("could not forget %s: %s", address, _reason(exc))

    def device_name(self, address: str) -> str:
        if address in self._device_names:
            return self._device_names[address]
        path = f"/org/bluez/{self.adapter}/dev_{address.upper().replace(':', '_')}"
        try:
            obj = self.bus.get_object(BLUEZ, path)
            props = obj.GetAll(
                "org.bluez.Device1", dbus_interface="org.freedesktop.DBus.Properties"
            )
            name = str(props.get("Name") or props.get("Alias") or address)
        except Exception:
            name = address
        self._device_names[address] = name
        return name

    # -- internals ---------------------------------------------------------
    def _adapter(self):
        import dbus
        return dbus.Interface(self.bus.get_object(BLUEZ, f"/org/bluez/{self.adapter}"),
                              "org.bluez.Adapter1")

    def _props(self):
        import dbus
        return dbus.Interface(self.bus.get_object(BLUEZ, f"/org/bluez/{self.adapter}"),
                              "org.freedesktop.DBus.Properties")

    def _manager(self):
        import dbus
        return dbus.Interface(self.bus.get_object(BLUEZ, "/org/bluez"),
                              "org.bluez.ProfileManager1")

    def _set(self, name: str, value) -> None:
        try:
            import dbus
            if isinstance(value, bool):
                value = dbus.Boolean(value)
            elif isinstance(value, int):
                value = dbus.UInt32(value)
            self._props().Set("org.bluez.Adapter1", name, value)
        except BluezError:
            raise
        except Exception as exc:
            raise BluezError(f"cannot set {name}: {_reason(exc)}") from exc

    def close(self) -> None:
        self.unregister_profile()
        self._bus = None


def _reason(exc: Exception) -> str:
    """Turn a dbus exception into something readable on a 320 px screen."""
    name = getattr(exc, "get_dbus_name", lambda: "")()
    if name == "org.bluez.Error.AlreadyExists":
        return "profile already registered"
    if name == "org.bluez.Error.NotPermitted":
        return "not permitted (run as root)"
    if name == "org.freedesktop.DBus.Error.ServiceUnknown":
        return "bluetooth service is not running"
    return str(exc).splitlines()[0][:80] or exc.__class__.__name__
