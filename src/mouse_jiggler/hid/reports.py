"""Mouse report encoding.

A report on the HIDP interrupt channel is:

    0xA1            DATA | input report
    0x02            report ID (see descriptor.py)
    buttons  dx  dy  wheel     four signed/bitfield bytes

All deltas are clamped to the int8 range the descriptor advertises.
"""

from __future__ import annotations

from .descriptor import BUTTON_MIDDLE, BUTTON_RIGHT, REPORT_ID, REPORT_SIZE

INT8_MIN, INT8_MAX = -127, 127
DATA_INPUT = 0xA1


def clamp(value: int, low: int = INT8_MIN, high: int = INT8_MAX) -> int:
    return max(low, min(high, int(value)))


def mouse_report(buttons: int = 0, dx: int = 0, dy: int = 0, wheel: int = 0) -> bytes:
    """Return the 4-byte report payload (no HIDP header, no report ID)."""
    return bytes(
        (
            buttons & (BUTTON_RIGHT | BUTTON_MIDDLE | 0x01),
            clamp(dx) & 0xFF,
            clamp(dy) & 0xFF,
            clamp(wheel) & 0xFF,
        )
    )


def input_payload(buttons: int = 0, dx: int = 0, dy: int = 0, wheel: int = 0) -> bytes:
    """Return the full payload to write on the interrupt channel."""
    report = mouse_report(buttons, dx, dy, wheel)
    assert len(report) == REPORT_SIZE
    return bytes((DATA_INPUT, REPORT_ID)) + report


IDLE_PAYLOAD = input_payload()
