import xml.etree.ElementTree as ET

from mouse_jiggler.bt.sdp import SDP_RECORD, make_sdp_record
from mouse_jiggler.hid.descriptor import DESCRIPTOR_HEX


def attributes(xml_text):
    root = ET.fromstring(xml_text)
    return {node.get("id"): node for node in root.findall("attribute")}


def test_record_is_well_formed_and_complete():
    attrs = attributes(SDP_RECORD)
    for required in ("0x0001", "0x0004", "0x0005", "0x0009", "0x000D", "0x0100",
                     "0x0202", "0x0206", "0x020B"):
        assert required in attrs


def test_descriptor_matches_the_hid_module():
    attrs = attributes(SDP_RECORD)
    hex_text = attrs["0x0206"].find(".//text[@encoding='hex']").get("value")
    assert hex_text == DESCRIPTOR_HEX


def test_mouse_subclass_and_language():
    attrs = attributes(SDP_RECORD)
    assert attrs["0x0202"].find("uint8").get("value") == "0x80"
    assert attrs["0x020B"].find("uint16").get("value") == "0x0000"


def test_names_are_xml_escaped():
    record = make_sdp_record(name="A & B", description="<mouse>")
    attrs = attributes(record)
    assert attrs["0x0100"].find("text").get("value") == "A & B"
    assert attrs["0x0101"].find("text").get("value") == "<mouse>"
