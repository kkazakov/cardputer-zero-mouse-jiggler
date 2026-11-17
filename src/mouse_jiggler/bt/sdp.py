"""SDP record for a Bluetooth HID mouse.

BlueZ accepts this XML verbatim through ProfileManager1.RegisterProfile. The
report descriptor is injected from hid/descriptor.py so the record can never
drift from the reports we actually send.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from ..constants import DEFAULT_DEVICE_NAME
from ..hid.descriptor import DESCRIPTOR_HEX

DEVICE_NAME = DEFAULT_DEVICE_NAME
DEVICE_DESCRIPTION = "Bluetooth mouse jiggler"
PROVIDER = "CardputerZero"


_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" ?>
<record>
  <attribute id="0x0001"><sequence><uuid value="0x1124"/></sequence></attribute>
  <attribute id="0x0004"><sequence>
      <sequence><uuid value="0x0100"/><uint16 value="0x0011"/></sequence>
      <sequence><uuid value="0x0011"/></sequence>
  </sequence></attribute>
  <attribute id="0x0005"><sequence><uuid value="0x1002"/></sequence></attribute>
  <attribute id="0x0006"><sequence>
      <uint16 value="0x656E"/><uint16 value="0x006A"/><uint16 value="0x0100"/>
  </sequence></attribute>
  <attribute id="0x0009"><sequence>
      <sequence><uuid value="0x1124"/><uint16 value="0x0100"/></sequence>
  </sequence></attribute>
  <attribute id="0x000D"><sequence><sequence>
      <sequence><uuid value="0x0100"/><uint16 value="0x0013"/></sequence>
      <sequence><uuid value="0x0011"/></sequence>
  </sequence></sequence></attribute>
  <attribute id="0x0100"><text value="{name}"/></attribute>
  <attribute id="0x0101"><text value="{description}"/></attribute>
  <attribute id="0x0102"><text value="{provider}"/></attribute>
  <attribute id="0x0200"><uint16 value="0x0100"/></attribute>
  <attribute id="0x0201"><uint16 value="0x0111"/></attribute>
  <attribute id="0x0202"><uint8 value="0x80"/></attribute>
  <attribute id="0x0203"><uint8 value="0x00"/></attribute>
  <attribute id="0x0204"><boolean value="false"/></attribute>
  <attribute id="0x0205"><boolean value="false"/></attribute>
  <attribute id="0x0206"><sequence><sequence>
      <uint8 value="0x22"/>
      <text encoding="hex" value="{descriptor}"/>
  </sequence></sequence></attribute>
  <attribute id="0x0207"><sequence>
      <sequence><uint16 value="0x0409"/><uint16 value="0x0100"/></sequence>
  </sequence></attribute>
  <attribute id="0x020B"><uint16 value="0x0000"/></attribute>
  <attribute id="0x020C"><uint16 value="0x0C80"/></attribute>
  <attribute id="0x020D"><boolean value="false"/></attribute>
  <attribute id="0x020E"><boolean value="false"/></attribute>
  <attribute id="0x020F"><uint16 value="0x0640"/></attribute>
  <attribute id="0x0210"><uint16 value="0x0320"/></attribute>
</record>
"""


def make_sdp_record(name: str = DEVICE_NAME, description: str = DEVICE_DESCRIPTION,
                    provider: str = PROVIDER) -> str:
    return _TEMPLATE.format(
        name=escape(name),
        description=escape(description),
        provider=escape(provider),
        descriptor=DESCRIPTOR_HEX,
    )


SDP_RECORD = make_sdp_record()
