import socket

import pytest

from mouse_jiggler.bt.hidp import control_reply, is_output_report
from mouse_jiggler.bt.server import HidClient
from mouse_jiggler.hid.reports import input_payload


@pytest.mark.parametrize("frame", [
    b"\x70",        # SET_IDLE, parameter 0
    b"\x71",        # SET_IDLE as some hosts send it
    b"\x90\x01",    # SET_PROTOCOL(report)
    b"\x90\x00",    # SET_PROTOCOL(boot)
    b"\x50\x02",    # SET_REPORT
    b"\x10\x04",    # HID_CONTROL resume
])
def test_control_transactions_are_acknowledged(frame):
    assert control_reply(frame) == b"\x00"


@pytest.mark.parametrize("frame", [b"\x40", b"\x80", b"\x60", b"\xAA"])
def test_unknown_or_unsupported_get_handshake_error(frame):
    assert control_reply(frame) == b"\x03"


def test_empty_frame_needs_no_reply():
    assert control_reply(b"") is None


def test_output_report_detection():
    assert is_output_report(b"\xA2\x02\x00\x00\x00\x00")
    assert not is_output_report(b"\xA1\x02\x00\x02\x00\x00")


def test_client_answers_control_channel():
    device, host = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    client = HidClient(address="AA:BB", ctl=device)
    try:
        host.send(b"\x71")
        assert client.handle_control() == b"\x00"
        host.send(b"\x90\x01")
        assert client.handle_control() == b"\x00"
    finally:
        client.close()
        host.close()


def test_closed_control_channel_raises():
    device, host = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    client = HidClient(address="AA:BB", ctl=device)
    host.close()
    with pytest.raises(ConnectionError):
        client.handle_control()
    client.close()


def test_send_mouse_writes_an_input_report():
    ctl_dev, ctl_host = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    int_dev, int_host = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    client = HidClient(address="AA:BB", ctl=ctl_dev, intr=int_dev)
    try:
        assert client.send_mouse(dx=2)
        assert int_host.recv(64) == input_payload(dx=2)
    finally:
        client.close()
        ctl_host.close()
        int_host.close()


def test_send_mouse_without_interrupt_channel_is_false():
    ctl_dev, ctl_host = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    client = HidClient(address="AA:BB", ctl=ctl_dev)
    try:
        assert client.send_mouse(dx=1) is False
    finally:
        client.close()
        ctl_host.close()


def test_busy_hid_channels_point_at_the_installer(monkeypatch):
    import errno

    from mouse_jiggler.bt.server import HidServer, HidServerError

    def busy(_self, _address, _psm):
        raise OSError(errno.EADDRINUSE, "Address already in use")

    monkeypatch.setattr(HidServer, "_listen", busy)
    with pytest.raises(HidServerError, match="bluetooth-fix"):
        HidServer().start("AA:BB:CC:DD:EE:FF")
