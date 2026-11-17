"""On-screen name editor for the raw evdev keypad.

The CardputerZero keymap emits ordinary letter/digit keycodes plus modifiers,
so a small explicit map is enough. Shift is tracked from KEY_LEFTSHIFT /
KEY_RIGHTSHIFT; the firmware's one-shot and lock modes are seen by us as a
normal press/release pair.

Typing is limited to letters, digits, space, ``-``, ``_`` and ``.`` — the
characters every host accepts in a Bluetooth name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..constants import MAX_DEVICE_NAME
from .keypad import (
    KEY_0,
    KEY_1,
    KEY_2,
    KEY_3,
    KEY_4,
    KEY_5,
    KEY_6,
    KEY_7,
    KEY_8,
    KEY_9,
    KEY_BACKSPACE,
    KEY_DOT,
    KEY_ENTER,
    KEY_F1,
    KEY_F2,
    KEY_F3,
    KEY_F4,
    KEY_F5,
    KEY_F6,
    KEY_F7,
    KEY_F8,
    KEY_F9,
    KEY_F10,
    KEY_KPENTER,
    KEY_LEFTSHIFT,
    KEY_MINUS,
    KEY_OK,
    KEY_RIGHTSHIFT,
    KEY_SPACE,
    KeyEvent,
)


class EditAction(Enum):
    NONE = "none"
    CHANGED = "changed"
    SUBMIT = "submit"


LETTERS: dict[int, str] = {}
for _i, _ch in enumerate("asdfghjkl"):
    LETTERS[30 + _i] = _ch
for _i, _ch in enumerate("zxcvbnm"):
    LETTERS[44 + _i] = _ch
for _i, _ch in enumerate("qwertyuiop"):
    LETTERS[16 + _i] = _ch
del _i, _ch

DIGITS = {
    KEY_1: "1", KEY_2: "2", KEY_3: "3", KEY_4: "4", KEY_5: "5",
    KEY_6: "6", KEY_7: "7", KEY_8: "8", KEY_9: "9", KEY_0: "0",
    KEY_F1: "1", KEY_F2: "2", KEY_F3: "3", KEY_F4: "4", KEY_F5: "5",
    KEY_F6: "6", KEY_F7: "7", KEY_F8: "8", KEY_F9: "9", KEY_F10: "0",
}

SHIFTED = {"-": "_"}


@dataclass
class NameEditor:
    max_length: int = MAX_DEVICE_NAME
    text: str = ""
    shift: bool = False
    replace_on_type: bool = False
    _shift_codes = (KEY_LEFTSHIFT, KEY_RIGHTSHIFT)
    _submit_codes = (KEY_ENTER, KEY_KPENTER, KEY_OK)
    _ignored_codes: set[int] = field(default_factory=set)

    def reset(self, initial: str = "", select_all: bool = False) -> None:
        self.text = initial[: self.max_length]
        self.shift = False
        # Mimic "select all": the first typed character replaces the old name.
        self.replace_on_type = bool(select_all and self.text)

    def handle(self, event: KeyEvent) -> EditAction:
        if event.code in self._shift_codes:
            self.shift = event.pressed
            return EditAction.NONE

        if not event.pressed:
            return EditAction.NONE

        if event.code in self._submit_codes:
            return EditAction.SUBMIT

        if event.code == KEY_BACKSPACE:
            self.replace_on_type = False
            if self.text:
                self.text = self.text[:-1]
                return EditAction.CHANGED
            return EditAction.NONE

        char = self._char_for(event.code)
        if char is None:
            return EditAction.NONE
        if self.replace_on_type:
            self.text = ""
            self.replace_on_type = False
        if len(self.text) >= self.max_length:
            return EditAction.NONE

        self.text += char
        return EditAction.CHANGED

    def _char_for(self, code: int) -> str | None:
        if code in LETTERS:
            char = LETTERS[code]
            return char.upper() if self.shift else char
        if code in DIGITS:
            return DIGITS[code]
        if code == KEY_SPACE:
            return " "
        if code == KEY_MINUS:
            return SHIFTED["-"] if self.shift else "-"
        if code == KEY_DOT:
            return "."
        return None

    def commit(self) -> str | None:
        name = " ".join(self.text.split()).strip()
        return name or None
