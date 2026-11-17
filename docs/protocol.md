# Bluetooth HID transport — protocol notes

Technical appendix to [PLAN.md](../PLAN.md). Everything below is what the app
implements to appear as a **classic Bluetooth mouse**; the code lives in
`src/mouse_jiggler/bt/` (SDP, profile, agent, L2CAP/HIDP server) and
`src/mouse_jiggler/hid/` (descriptor, reports). The spike in §9 is still the
first thing to run on a new device image. Verified against
BlueZ's D-Bus API and PiKVM's working implementation (`kvmd/plugins/hid/bt`),
but **must be re-verified on CardputerZero firmware in milestone M0** — that is
what the spike at the end is for.

## 1. Transport decision

| Option | How it works | Verdict |
| --- | --- | --- |
| **Classic HID device (HIDP over L2CAP)** | Register the HID SDP record with BlueZ `ProfileManager1`, then bind L2CAP PSMs `0x11` (control) and `0x13` (interrupt) yourself and speak HIDP | **Chosen** — proven on Raspberry Pi by PiKVM, no kernel modules, ~400 lines |
| BLE HID over GATT (HOGP) | GATT server with HID service + Report Map + Report characteristic; advertise as peripheral (e.g. `bluez-peripheral`) | Fallback. Works on modern hosts, but more moving parts (advertising, CCCD, MTU) and more host quirks |
| `/dev/uhid` + kernel | Create a HID device node, let the kernel own reports | Rejected: needs `CONFIG_UHID`, makes the *local* box see the mouse too, and BlueZ has no HID-device profile to drive it |
| USB HID gadget | `configfs` gadget on the USB-C port | Out of scope (wired), but the cheapest fallback if Bluetooth fails |

Classic HID was chosen because the whole device side is: one SDP record, two
sockets, and a 4-byte report. No kernel modules, no firmware-specific drivers.

## 2. Stack map

```
┌─────────────────────────────── CardputerZero ───────────────────────────────┐
│  mouse-jiggler (Python, root via APPLaunch)                                 │
│    ├── dbus  ──► bluetoothd (org.bluez)                                     │
│    │              ProfileManager1.RegisterProfile(HID UUID, SDP XML)        │
│    │              Adapter1.{Powered,Pairable,Discoverable,Alias,Class}      │
│    │              AgentManager1 (auto-accept "Just Works" pairing)          │
│    └── AF_BLUETOOTH/L2CAP sockets                                           │
│           PSM 0x11 control  ◄── SET_IDLE / SET_PROTOCOL / GET_REPORT        │
│           PSM 0x13 interrupt ──► 0xA1 + report ID + [btn,x,y,wheel]         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲  BR/EDR
                              ┌─────┴─────┐
                              │  Host OS  │  Windows / macOS / Linux
                              └───────────┘
```

BlueZ owns discovery, SDP and pairing; the app owns the two data channels.
The adapter must be powered, and the app needs root (or
`CAP_NET_BIND_SERVICE`) to bind PSMs below 4096.

## 3. Registering the profile

```python
import dbus

HID_UUID = "00001124-0000-1000-8000-00805F9B34FB"

bus = dbus.SystemBus()
manager = dbus.Interface(
    bus.get_object("org.bluez", "/org/bluez"),
    "org.bluez.ProfileManager1",
)

manager.RegisterProfile(
    "/org/bluez/mousejiggler",          # object path, must be unique
    HID_UUID,
    {
        "ServiceRecord": SDP_XML,       # string, see §4
        "Role": "server",
        "RequireAuthentication": True,  # bonded hosts only
        "RequireAuthorization": False,
    },
)
```

- Register **before** the first host connects; the record is what makes the
  device discoverable as a mouse.
- If the process died without unregistering, the next start gets
  `org.bluez.Error.AlreadyExists` — catch it, call `UnregisterProfile`, retry.
- Unregister on clean exit, otherwise a stale SDP record survives until
  `bluetoothd` restarts.

Adapter properties (via `org.freedesktop.DBus.Properties` on
`/org/bluez/hci0`):

| Property | Value | Why |
| --- | --- | --- |
| `Powered` | `true` | radio on |
| `Alias` | `CardputerZero Mouse` | name hosts show |
| `Class` | `0x000580` | peripheral / pointing device (cosmetic icon) |
| `Pairable` | `true` only while pairing | don't let strangers pair |
| `Discoverable` | `true` only while pairing | invisible otherwise |

`DiscoverableTimeout` (seconds, `0` = forever) can auto-expire discovery, but
the app keeps its own 180 s countdown so the UI matches reality.

## 4. SDP record (mouse only)

`HIDDeviceSubclass = 0x80` (mouse), `HIDBootDeviceType = 0x0000` (report
protocol only). The `<text encoding="hex">` value is the report descriptor from
§5.

```xml
<?xml version="1.0" encoding="UTF-8" ?>
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
  <attribute id="0x0100"><text value="CardputerZero Mouse"/></attribute>
  <attribute id="0x0101"><text value="Bluetooth mouse jiggler"/></attribute>
  <attribute id="0x0102"><text value="CardputerZero"/></attribute>
  <attribute id="0x0200"><uint16 value="0x0100"/></attribute>
  <attribute id="0x0201"><uint16 value="0x0111"/></attribute>
  <attribute id="0x0202"><uint8 value="0x80"/></attribute>
  <attribute id="0x0203"><uint8 value="0x00"/></attribute>
  <attribute id="0x0204"><boolean value="false"/></attribute>
  <attribute id="0x0205"><boolean value="false"/></attribute>
  <attribute id="0x0206"><sequence><sequence>
      <uint8 value="0x22"/>
      <text encoding="hex" value="05010902A10185020901A100050919012903150025019503750181029501750581030501093009311581257F75089502810609381581257F750895018106C0C0"/>
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
```

Attribute notes: `0x0004` = L2CAP/PSM 17 + HIDP, `0x000D` = the interrupt
channel (PSM 19), `0x0206` = HID descriptor list, `0x020B` = boot device type,
`0x020C`–`0x0210` = SSR/latency parameters (copied from PiKVM, hosts tolerate
them).

## 5. Report descriptor and reports

64-byte descriptor: 3 buttons, 5-bit padding, 8-bit relative X/Y, 8-bit wheel,
**report ID 2**.

```
05 01 09 02 A1 01 85 02 09 01 A1 00
05 09 19 01 29 03 15 00 25 01 95 03 75 01 81 02
95 01 75 05 81 03
05 01 09 30 09 31 15 81 25 7F 75 08 95 02 81 06
09 38 15 81 25 7F 75 08 95 01 81 06
C0 C0
```

Report layout on the wire (interrupt channel):

```
A1 02 [buttons] [dx] [dy] [wheel]
│  │  └ 3 bits, 0 = no button
│  └ report ID 2 (must match 85 02 above)
└ DATA | input report
```

`dx`, `dy`, `wheel` are **signed 8-bit** (-127..127). Examples:

| Action | Bytes |
| --- | --- |
| move +2 px right | `A1 02 00 02 00 00` |
| move -2 px (alternating slow tick) | `A1 02 00 FE 00 00` |
| jiggle +25/-18 | `A1 02 00 19 EE 00` |
| stop / clear | `A1 02 00 00 00 00` |

The 8-bit range is why jiggle vectors are clamped to ±30 and why a mode can
never exceed ±127 in one report (all three modes are far below).

## 6. HIDP control channel

Match on the high nibble (`data[0] & 0xF0`) and reply on the same socket.
Hosts are inconsistent about the low nibble — PiKVM compares `0x71` literally.

| Header | Message | Reply |
| --- | --- | --- |
| `0x70` | SET_IDLE | `HANDSHAKE 0x00` (success) |
| `0x90` | SET_PROTOCOL (`0x00` boot, `0x01` report) | `0x00`; we stay in report mode (boot not advertised) |
| `0x40` | GET_REPORT | `A1 02 …` current report, or `0x03` unsupported |
| `0x50` | SET_REPORT | `0x00` |
| `0x10` | HID_CONTROL (suspend/resume) | `0x00`; optionally pause reports while suspended |
| `0x60` | GET_IDLE | `0x03` (unsupported) |

Handshake codes: `0x00` success, `0x01` not ready, `0x02` invalid report ID,
`0x03` unsupported request, `0x04` invalid parameter.

On the interrupt channel the host may send `0xA2 …` (output report). For a
mouse there is nothing to do — read and discard.

## 7. Pairing and bonding

1. `Pairable=true`, `Discoverable=true` (180 s), agent registered with
   capability `NoInputNoOutput` → SSP "Just Works".
2. Host selects the device, connects the control channel, triggers pairing.
3. The app's `org.bluez.Agent1` auto-accepts:
   `RequestConfirmation`, `RequestAuthorization`, `AuthorizeService` → return;
   `RequestPinCode` → `"0000"`; `DisplayPasskey`/`DisplayPinCode` → log only.
4. BlueZ stores the link key in `/var/lib/bluetooth/<adapter>/<host>/`.
5. After pairing, drop `Discoverable`/`Pairable`; only the bonded host can
   reconnect (profile has `RequireAuthentication=true`).

Check during M0 that `/var/lib/bluetooth` is on persistent storage — some
images mount it as tmpfs (PiKVM does), which would lose bonds at reboot.

Reconnect is host-initiated: keep the two PSM listeners open for the app's
whole lifetime and the host will page the device when it wants the mouse. If
the host does not reconnect, the fallback is `Device1.Connect()` on the last
bonded device path after startup.

## 8. Permissions

Binding L2CAP PSMs 17/19 needs `CAP_NET_BIND_SERVICE` (PSMs < 4096 are
privileged). APPLaunch starts apps as root, so this is satisfied in the normal
path. Manual runs need `sudo`. A capability-only setup is possible but awkward
for a Python entry point — treat root as a requirement and say so in the UI
when a bind fails with `EACCES`.

## 9. M0 spike (verified 2026-11-16)

> **Result: passed.** A Linux host paired, enumerated `CardputerZero Mouse` as a
> mouse and received `REL_X ±3` events. Full evidence:
> [hardware-verification.md](hardware-verification.md). One deployment
> requirement came out of it: run bluetoothd with `-P input`, otherwise its
> input plugin keeps PSMs 17/19 bound (`install.sh bluetooth-fix`).

## 9.1 Spike script (≈80 lines, run on the device)

Purpose: prove the whole chain — profile registration, pairing, report — before
writing any app code. Success = the host cursor moves 2 px every 2 s.

```python
#!/usr/bin/env python3
"""M0 spike. Run as root on the CardputerZero. Ctrl-C to stop."""
import select
import socket
import time

import dbus

ADAPTER = "hci0"
HID_UUID = "00001124-0000-1000-8000-00805F9B34FB"
PSM_CTRL, PSM_INTR = 17, 19
SDP_XML = open("sdp_mouse.xml", encoding="utf-8").read()   # §4

bus = dbus.SystemBus()
adapter = bus.get_object("org.bluez", f"/org/bluez/{ADAPTER}")
props = dbus.Interface(adapter, "org.freedesktop.DBus.Properties")
manager = dbus.Interface(bus.get_object("org.bluez", "/org/bluez"),
                         "org.bluez.ProfileManager1")

try:
    manager.UnregisterProfile("/org/bluez/spike")
except dbus.DBusException:
    pass
manager.RegisterProfile("/org/bluez/spike", HID_UUID, {
    "ServiceRecord": SDP_XML,
    "Role": "server",
    "RequireAuthentication": True,
    "RequireAuthorization": False,
})
for key, value in (("Powered", True), ("Alias", "CardputerZero Mouse"),
                   ("Class", dbus.UInt32(0x000580)),
                   ("Pairable", True), ("Discoverable", True)):
    props.Set("org.bluez.Adapter1", key, value)

addr = str(props.Get("org.bluez.Adapter1", "Address"))


def listen(psm):
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET,
                         socket.BTPROTO_L2CAP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((addr, psm))
    sock.listen(1)
    return sock


ctl, intr = listen(PSM_CTRL), listen(PSM_INTR)
print("pair with 'CardputerZero Mouse' from the host; waiting…")

conn = None
while True:
    ready, _, _ = select.select([ctl, intr], [], [], 1.0)
    for sock in ready:
        client, peer = sock.accept()
        print("channel open:", peer, "psm", PSM_CTRL if sock is ctl else PSM_INTR)
        if sock is intr:
            conn = client
    if conn is None:
        continue
    try:
        conn.send(bytes([0xA1, 0x02, 0x00, 0x02, 0x00, 0x00]))   # +2 px
        time.sleep(2)
        conn.send(bytes([0xA1, 0x02, 0x00, 0xFE, 0x00, 0x00]))   # -2 px
        time.sleep(2)
    except OSError as exc:
        print("link lost:", exc)
        conn = None
```

Diagnostics when it fails:

```bash
bluetoothctl show                     # powered? discoverable?
bluetoothctl devices                  # bond present?
journalctl -u bluetooth -n 50         # profile/pairing errors
busctl tree org.bluez                 # profile object registered?
python3 -c "import dbus, socket; print(socket.AF_BLUETOOTH, socket.BTPROTO_L2CAP)"
```

## 10. References

- BlueZ profile API — <https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/profile-api.txt>
- BlueZ agent API — <https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/agent-api.txt>
- HID Profile 1.1 (HIDP, SDP attributes) — Bluetooth SIG
- PiKVM implementation — <https://github.com/pikvm/kvmd/tree/master/kvmd/plugins/hid/bt>
- Linux HIDP constants — `include/net/bluetooth/hidp.h`
- PiKVM Bluetooth HID guide — <https://github.com/pikvm/pikvm/blob/master/docs/bluetooth_hid.md>
