"""Name editor: key mapping, shift, limits and commit rules."""

from mouse_jiggler.input.keypad import (
    KEY_A,
    KEY_BACKSPACE,
    KEY_D,
    KEY_ENTER,
    KEY_K,
    KEY_LEFTSHIFT,
    KEY_MINUS,
    KEY_SPACE,
    KeyEvent,
)
from mouse_jiggler.input.text import EditAction, NameEditor


def type_text(editor, text):
    for char in text:
        code = {
            "d": KEY_D, "k": KEY_K, "a": KEY_A, " ": KEY_SPACE, "-": KEY_MINUS,
        }.get(char)
        if code is None:
            code = ord(char.upper()) - ord("A") + 30  # not used in these tests
        editor.handle(KeyEvent(code, True))


def test_types_lowercase_and_space():
    editor = NameEditor()
    editor.reset("", select_all=False)
    type_text(editor, "dk a")
    assert editor.text == "dk a"


def test_shift_makes_uppercase_and_underscore():
    editor = NameEditor()
    editor.reset("", select_all=False)
    editor.handle(KeyEvent(KEY_LEFTSHIFT, True))
    editor.handle(KeyEvent(KEY_D, True))
    editor.handle(KeyEvent(KEY_LEFTSHIFT, False))
    editor.handle(KeyEvent(KEY_A, True))
    editor.handle(KeyEvent(KEY_LEFTSHIFT, True))
    editor.handle(KeyEvent(KEY_MINUS, True))
    editor.handle(KeyEvent(KEY_LEFTSHIFT, False))
    assert editor.text == "Da_"


def test_backspace_removes_last_character():
    editor = NameEditor()
    editor.reset("abc", select_all=False)
    editor.handle(KeyEvent(KEY_BACKSPACE, True))
    assert editor.text == "ab"


def test_select_all_replaces_on_first_character():
    editor = NameEditor()
    editor.reset("CardputerZero Mouse", select_all=True)
    editor.handle(KeyEvent(KEY_D, True))
    assert editor.text == "d"


def test_backspace_cancels_select_all():
    editor = NameEditor()
    editor.reset("old", select_all=True)
    editor.handle(KeyEvent(KEY_BACKSPACE, True))
    assert editor.text == "ol"
    assert editor.replace_on_type is False


def test_max_length_is_enforced():
    editor = NameEditor(max_length=4)
    editor.reset("", select_all=False)
    type_text(editor, "ddddd")
    assert editor.text == "dddd"


def test_submit_action():
    editor = NameEditor()
    editor.reset("x", select_all=False)
    assert editor.handle(KeyEvent(KEY_ENTER, True)) is EditAction.SUBMIT


def test_commit_trims_and_rejects_empty():
    editor = NameEditor()
    editor.reset("  Desk   Mouse  ", select_all=False)
    assert editor.commit() == "Desk Mouse"

    editor.reset("   ", select_all=False)
    assert editor.commit() is None
