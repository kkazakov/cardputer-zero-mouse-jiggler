"""HID report descriptor for a 3-button relative mouse with a wheel.

64 bytes, report ID 2, four-byte reports:

    byte 0   buttons (bit0 left, bit1 right, bit2 middle) + 5 padding bits
    byte 1   X, signed 8-bit relative
    byte 2   Y, signed 8-bit relative
    byte 3   wheel, signed 8-bit relative

The descriptor is advertised both in the SDP record (attribute 0x0206) and,
implicitly, by the reports we send on the interrupt channel. Keep the two in
sync: report ID 2 is part of the wire format.
"""

from __future__ import annotations

REPORT_ID = 2
REPORT_SIZE = 4

DESCRIPTOR = bytes.fromhex(
    "05010902A10185020901A100"
    "05091901290315002501950375018102950175058103"
    "0501093009311581257F750895028106"
    "09381581257F750895018106"
    "C0C0"
)

DESCRIPTOR_HEX = DESCRIPTOR.hex().upper()

BUTTON_LEFT = 0x01
BUTTON_RIGHT = 0x02
BUTTON_MIDDLE = 0x04

assert len(DESCRIPTOR) == 64
