"""Raw evdev reader for the CardputerZero keyboard.

No python-evdev dependency: input_event structures are 24 bytes on 64-bit
Linux and parsing them is a two-line struct unpack. The tca8418 keypad is found
through sysfs, with the by-path node as the fast path.
"""

from __future__ import annotations

import glob
import logging
import os
import struct
from dataclasses import dataclass

log = logging.getLogger(__name__)

EV_KEY = 0x01
EVENT = struct.Struct("<qqHHi")

KEY_ESC = 1
KEY_1, KEY_2, KEY_3, KEY_4, KEY_5 = 2, 3, 4, 5, 6
KEY_6, KEY_7, KEY_8, KEY_9, KEY_0 = 7, 8, 9, 10, 11
KEY_MINUS = 12
KEY_BACKSPACE = 14
KEY_Q, KEY_W, KEY_E, KEY_R, KEY_T, KEY_Y, KEY_U, KEY_I, KEY_O, KEY_P = range(16, 26)
KEY_A, KEY_S, KEY_D, KEY_F, KEY_G, KEY_H, KEY_J, KEY_K, KEY_L = range(30, 39)
KEY_Z, KEY_X, KEY_C, KEY_V, KEY_B, KEY_N, KEY_M = range(44, 51)
KEY_DOT = 52
KEY_SPACE = 57
KEY_F1, KEY_F2, KEY_F3, KEY_F4, KEY_F5 = 59, 60, 61, 62, 63
KEY_F6, KEY_F7, KEY_F8, KEY_F9, KEY_F10 = 64, 65, 66, 67, 68
KEY_ENTER = 28
KEY_KPENTER = 96
KEY_RIGHTSHIFT = 54
KEY_LEFTSHIFT = 42
KEY_LEFT = 105
KEY_RIGHT = 106
KEY_OK = 352  # newer kernels; also emitted by some firmware as "OK"

BY_PATH = "/dev/input/by-path/platform-3f804000.i2c-event"

#: keys the app reacts to, mapped to semantic names
NAMES = {
    KEY_ESC: "esc",
    KEY_ENTER: "ok",
    KEY_KPENTER: "ok",
    KEY_OK: "ok",
    KEY_Z: "prev",
    KEY_LEFT: "prev",
    KEY_C: "next",
    KEY_RIGHT: "next",
}


@dataclass(frozen=True)
class KeyEvent:
    code: int
    pressed: bool


class KeypadError(RuntimeError):
    pass


def parse_events(data: bytes) -> tuple[list[KeyEvent], bytes]:
    """Decode as many complete input_event records as possible."""
    events: list[KeyEvent] = []
    offset = 0
    while offset + EVENT.size <= len(data):
        _sec, _usec, kind, code, value = EVENT.unpack_from(data, offset)
        offset += EVENT.size
        if kind != EV_KEY or value == 2:
            continue
        events.append(KeyEvent(code=code, pressed=value != 0))
    return events, data[offset:]


def find_device() -> str | None:
    if os.path.exists(BY_PATH):
        return BY_PATH
    for name_path in sorted(glob.glob("/sys/class/input/event*/device/name")):
        try:
            with open(name_path, encoding="utf-8", errors="replace") as fh:
                name = fh.read().strip().lower()
        except OSError:
            continue
        if any(token in name for token in ("tca8418", "keypad", "m5stack", "cardputer")):
            return "/dev/input/" + name_path.split("/")[4]
    return None


class Keypad:
    def __init__(self, fd: int, path: str) -> None:
        self.fd = fd
        self.path = path
        self._buffer = b""

    @classmethod
    def open(cls, path: str | None = None) -> Keypad:
        target = path or find_device()
        if not target:
            raise KeypadError("no CardputerZero keypad found (use --keys /dev/input/eventN)")
        try:
            fd = os.open(target, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as exc:
            raise KeypadError(f"cannot open {target}: {exc}") from exc
        log.info("keyboard: %s", target)
        return cls(fd, target)

    def poll(self) -> list[KeyEvent]:
        chunks = bytearray()
        while True:
            try:
                chunk = os.read(self.fd, 4096)
            except BlockingIOError:
                break
            except OSError as exc:
                log.warning("keyboard read failed: %s", exc)
                break
            if not chunk:
                break
            chunks.extend(chunk)
        if not chunks:
            return []
        events, self._buffer = parse_events(bytes(self._buffer) + bytes(chunks))
        return events

    def close(self) -> None:
        try:
            os.close(self.fd)
        except OSError:
            pass
