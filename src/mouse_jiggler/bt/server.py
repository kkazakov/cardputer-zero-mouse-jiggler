"""L2CAP HIDP server: two listening channels plus per-host sessions.

PSM 0x11 carries interrupt reports (device -> host), PSM 0x13 carries control
transactions. Binding PSMs below 4096 needs root or CAP_NET_BIND_SERVICE. Under
APPLaunch the app runs as the desktop user holding only that one capability
(packaging/caplaunch.c), with ``sudo -n`` as the fallback.

The socket creation is isolated in :meth:`HidServer._listen` so tests can drive
:class:`HidClient` over AF_UNIX socketpairs without a Bluetooth adapter.
"""

from __future__ import annotations

import errno
import logging
import select
import socket
from dataclasses import dataclass

from ..hid.reports import input_payload
from .hidp import PSM_CONTROL, PSM_INTERRUPT, control_reply, is_output_report

log = logging.getLogger(__name__)


class HidServerError(RuntimeError):
    pass


@dataclass
class HidClient:
    """One connected host: control + interrupt channel."""

    address: str
    ctl: socket.socket
    intr: socket.socket | None = None
    name: str = ""

    def handle_control(self) -> bytes | None:
        """Read one control message and return the reply, if any."""
        data = self.ctl.recv(1024)
        if not data:
            raise ConnectionError("control channel closed")
        return control_reply(data)

    def handle_interrupt_input(self) -> None:
        """Drain host output reports (mouse LEDs are not interesting)."""
        if self.intr is None:
            return
        data = self.intr.recv(1024)
        if not data:
            raise ConnectionError("interrupt channel closed")
        if not is_output_report(data):
            log.debug("ignoring interrupt payload %s", data[:4].hex())

    def send_mouse(self, dx: int = 0, dy: int = 0, buttons: int = 0, wheel: int = 0) -> bool:
        if self.intr is None:
            return False
        try:
            self.intr.send(input_payload(buttons, dx, dy, wheel))
            return True
        except OSError as exc:
            log.info("report to %s failed: %s", self.address, exc)
            self.close_interrupt()
            return False

    def close_interrupt(self) -> None:
        if self.intr is not None:
            _safe_close(self.intr)
            self.intr = None

    def close(self) -> None:
        self.close_interrupt()
        _safe_close(self.ctl)
        self.ctl = None  # type: ignore[assignment]

    @property
    def connected(self) -> bool:
        return self.intr is not None


class HidServer:
    def __init__(self) -> None:
        self._listeners: list[socket.socket] = []
        self._clients: dict[str, HidClient] = {}
        self._address = ""

    # -- lifecycle ---------------------------------------------------------
    def start(self, adapter_address: str) -> None:
        self._address = adapter_address
        self._listeners = []
        try:
            for psm in (PSM_CONTROL, PSM_INTERRUPT):
                self._listeners.append(self._listen(adapter_address, psm))
        except PermissionError as exc:
            self.close()
            raise HidServerError(
                "binding L2CAP PSMs needs CAP_NET_BIND_SERVICE "
                "(run as root or through the capability launcher)"
            ) from exc
        except OSError as exc:
            self.close()
            if exc.errno == errno.EADDRINUSE:
                raise HidServerError(
                    "HID channels busy: run `sudo ./install.sh bluetooth-fix` "
                    "(bluetoothd holds PSMs 17/19 via its input plugin)"
                ) from exc
            raise HidServerError(f"cannot open HID channels: {exc}") from exc
        log.info("listening for HID hosts on %s (PSM 0x11/0x13)", adapter_address)

    def close(self) -> None:
        for client in list(self._clients.values()):
            client.close()
        self._clients.clear()
        for listener in self._listeners:
            _safe_close(listener)
        self._listeners = []

    # -- polling -----------------------------------------------------------
    def poll(self, timeout: float = 0.0) -> None:
        listeners = self._listeners
        if not listeners:
            return
        watch = list(listeners)
        for client in self._clients.values():
            watch.append(client.ctl)
            if client.intr is not None:
                watch.append(client.intr)
        try:
            readable, _, _ = select.select(watch, [], [], timeout)
        except (OSError, ValueError):
            self.close()
            return

        for sock in readable:
            if sock in listeners:
                self._accept(sock)
                continue
            client = self._client_for(sock)
            if client is None:
                continue
            try:
                if sock is client.ctl:
                    reply = client.handle_control()
                    if reply:
                        client.ctl.send(reply)
                else:
                    client.handle_interrupt_input()
            except (ConnectionError, OSError) as exc:
                log.info("host %s disconnected: %s", client.address, exc)
                self._drop(client)

    def drop_host(self) -> None:
        """Close every connected host (used before re-pairing)."""
        for client in list(self._clients.values()):
            client.close()
        self._clients.clear()

    # -- reports -----------------------------------------------------------
    def send_mouse(self, dx: int = 0, dy: int = 0, buttons: int = 0, wheel: int = 0) -> int:
        sent = 0
        for client in list(self._clients.values()):
            if client.send_mouse(dx, dy, buttons, wheel):
                sent += 1
            elif not client.connected:
                self._drop(client)
        return sent

    @property
    def connected(self) -> bool:
        return any(client.connected for client in self._clients.values())

    @property
    def host_address(self) -> str:
        for client in self._clients.values():
            if client.connected:
                return client.address
        return ""

    @property
    def clients(self) -> list[HidClient]:
        return list(self._clients.values())

    # -- internals ---------------------------------------------------------
    def _listen(self, address: str, psm: int) -> socket.socket:
        sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((address, psm))
        sock.listen(1)
        sock.setblocking(False)
        return sock

    def _accept(self, listener: socket.socket) -> None:
        try:
            conn, peer = listener.accept()
        except (BlockingIOError, OSError):
            return
        conn.setblocking(True)
        address = str(peer[0]) if isinstance(peer, tuple) else str(peer)
        client = self._clients.get(address)
        if client is None:
            client = HidClient(address=address, ctl=conn)
            self._clients[address] = client
        if listener is self._listeners[0]:
            if client.ctl is not conn:
                _safe_close(client.ctl)
            client.ctl = conn
        else:
            client.close_interrupt()
            client.intr = conn
        log.info("HID channel accepted from %s", address)

    def _client_for(self, sock: socket.socket) -> HidClient | None:
        for client in self._clients.values():
            if sock is client.ctl or sock is client.intr:
                return client
        return None

    def _drop(self, client: HidClient) -> None:
        client.close()
        self._clients.pop(client.address, None)


def _safe_close(sock: socket.socket | None) -> None:
    if sock is None:
        return
    try:
        sock.close()
    except OSError:
        pass
