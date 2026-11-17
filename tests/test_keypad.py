from mouse_jiggler.input.keypad import EVENT, KEY_C, KEY_ESC, parse_events


def record(code, value):
    return EVENT.pack(0, 0, 1, code, value)


def test_parses_press_and_release():
    events, rest = parse_events(record(KEY_C, 1) + record(KEY_C, 0))
    assert [(e.code, e.pressed) for e in events] == [(KEY_C, True), (KEY_C, False)]
    assert rest == b""


def test_keeps_incomplete_tail_for_next_read():
    data = record(KEY_ESC, 1)
    events, rest = parse_events(data + b"\x00" * 5)
    assert len(events) == 1
    assert rest == b"\x00" * 5


def test_autorepeat_is_ignored():
    events, _ = parse_events(record(KEY_C, 2))
    assert events == []


def test_non_key_events_are_ignored():
    events, _ = parse_events(EVENT.pack(0, 0, 2, KEY_C, 1))  # EV_REL
    assert events == []
