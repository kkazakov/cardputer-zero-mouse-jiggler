"""HIDP framing helpers (control channel).

The HID profile uses two L2CAP channels:

* PSM 0x11, interrupt: device -> host DATA reports (`0xA1 ...`), host -> device
  output reports (`0xA2 ...`) which a mouse can ignore.
* PSM 0x13, control: handshake / idle / protocol transactions.

Only the control channel needs real answers. Hosts are inconsistent about the
low nibble (some send 0x71 for SET_IDLE), so dispatch on the high nibble.
"""

from __future__ import annotations

HANDSHAKE_SUCCESS = 0x00
HANDSHAKE_UNSUPPORTED = 0x03

TRANS_HID_CONTROL = 0x10
TRANS_GET_REPORT = 0x40
TRANS_SET_REPORT = 0x50
TRANS_GET_IDLE = 0x60
TRANS_SET_IDLE = 0x70
TRANS_GET_PROTOCOL = 0x80
TRANS_SET_PROTOCOL = 0x90
TRANS_DATA = 0xA0

DATA_INPUT = 0xA1
DATA_OUTPUT = 0xA2

PSM_CONTROL = 0x11
PSM_INTERRUPT = 0x13


def control_reply(data: bytes) -> bytes | None:
    """Return the bytes to send back, or None if the frame needs no reply."""
    if not data:
        return None
    transaction = data[0] & 0xF0
    if transaction in (
        TRANS_SET_IDLE,
        TRANS_SET_PROTOCOL,
        TRANS_SET_REPORT,
        TRANS_HID_CONTROL,
    ):
        return bytes((HANDSHAKE_SUCCESS,))
    # GET_REPORT / GET_IDLE / unknown: no data to offer, answer politely so the
    # host does not wait for a timeout.
    return bytes((HANDSHAKE_UNSUPPORTED,))


def is_output_report(data: bytes) -> bool:
    return bool(data) and data[0] == DATA_OUTPUT
