from mouse_jiggler.hid import descriptor, reports


def test_descriptor_is_64_bytes_with_report_id_2():
    assert len(descriptor.DESCRIPTOR) == 64
    assert descriptor.DESCRIPTOR.hex().upper() == descriptor.DESCRIPTOR_HEX
    assert descriptor.REPORT_ID == 2
    assert "8502" in descriptor.DESCRIPTOR_HEX


def test_positive_report_matches_golden_bytes():
    assert reports.input_payload(dx=2) == b"\xA1\x02\x00\x02\x00\x00"


def test_negative_report_uses_twos_complement():
    assert reports.input_payload(dx=-2) == b"\xA1\x02\x00\xFE\x00\x00"


def test_buttons_and_wheel():
    payload = reports.input_payload(buttons=0x03, dx=0, dy=-3, wheel=1)
    assert payload == b"\xA1\x02\x03\x00\xFD\x01"


def test_values_are_clamped_to_int8():
    payload = reports.input_payload(dx=400, dy=-400)
    assert payload[3] == 127
    assert payload[4] == 0x81


def test_idle_payload_is_a_zero_report():
    assert reports.IDLE_PAYLOAD == b"\xA1\x02\x00\x00\x00\x00"
