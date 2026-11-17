# Troubleshooting

Start with the error page: it shows the reason BlueZ or the framebuffer gave.
Then reproduce manually with debug logging:

```bash
sudo /usr/share/APPLaunch/bin/mouse-jiggler --debug
```

## The app is not in APPLaunch

```bash
ls /usr/share/APPLaunch/applications/mouse-jiggler.desktop
ls /usr/share/APPLaunch/bin/mouse-jiggler
ls /usr/share/APPLaunch/share/images/mouse-jiggler.png
sudo systemctl restart APPLaunch.service
```

The launcher only registers entries under `applications/*.desktop` that contain
`[Desktop Entry]`, `Name` and `Exec`. A relative `Exec` such as
`bin/mouse-jiggler` resolves under `/usr/share/APPLaunch`; if the file is not
executable, the entry silently fails.

## “Bluetooth adapter hci0 is not available”

```bash
bluetoothctl list
bluetoothctl show
rfkill list
sudo systemctl status bluetooth --no-pager
```

- Soft-blocked radio: `sudo rfkill unblock bluetooth`.
- No adapter listed: the UART-attached Bluetooth is not probed. Reboot; check
  `dmesg | grep -i blue`.
- The adapter is not `hci0` (HDMI/USB dongles can change numbering): run with
  `--adapter hci1`.
- `bluetoothd` not running: `sudo systemctl restart bluetooth`.

## “HID channels busy” / `Address already in use`

BlueZ's `input` plugin holds PSMs 0x11/0x13 for its own HID device role. Stop
it from loading:

```bash
sudo ./install.sh bluetooth-fix
```

This is required for the app to work at all on the stock image. It disables
Bluetooth HID **host** support; `sudo ./install.sh bluetooth-restore` reverts
it. Verify with:

```bash
systemctl cat bluetooth | grep ExecStart     # should show -P input
```

## “binding L2CAP PSMs needs CAP_NET_BIND_SERVICE”

The process holds no `CAP_NET_BIND_SERVICE`, so binding PSMs 17/19 fails with
`EACCES`. Two things can supply it — root, or the capability launcher — and
neither did. Start from the doctor on the device:

```bash
./install.sh doctor      # as the desktop user; as root it re-runs itself
```

| Doctor says | What to do |
| --- | --- |
| `missing: install.sh did not build it` | no C compiler at install time: `sudo apt install gcc` (or install the `.deb`, whose `postinst` sets it up), then `sudo ./install.sh` |
| `no file capability` | `sudo setcap cap_net_bind_service=pie /usr/lib/mouse-jiggler/caplaunch` |
| `mounted nosuid` | file capabilities are dropped there; the launcher belongs in `/usr/lib` |
| `CAP_NET_BIND_SERVICE does not reach python3` | the launcher itself ran without the capability; `bin/mouse-jiggler` then falls back to `sudo -n` |
| `the interpreter carries file capabilities` | remove them: `sudo setcap -r /usr/bin/python3.13` |
| `Address already in use` | see the bluetoothd section above |

A file capability on `/usr/bin/python3` is the subtle case: the kernel zeroes
the ambient set when `execve()` runs a privileged file, so the launcher's
`CAP_NET_BIND_SERVICE` never arrives and Python inherits the interpreter's
capability instead (`CapEff 0x2000` = `CAP_NET_RAW`, `CapAmb 0`). It also hands
that capability to every Python program on the device, so removing it is a
security fix as well.

Manual runs need the capability too — `python3 -m mouse_jiggler` on its own never
gets it:

```bash
sudo /usr/share/APPLaunch/bin/mouse-jiggler --debug
```

`0.2.6` packages built on a machine without an aarch64 cross compiler shipped an
empty `/usr/lib/mouse-jiggler/` (no launcher, no `postinst`), so those packages
always ran as root through `sudo -n`. Rebuild with `gcc-aarch64-linux-gnu`
installed.

## The host does not see “CardputerZero Mouse”

- The device must be in the **pairing** state (page with countdown). Check on
  the device: `bluetoothctl show` should report `Discoverable: yes` and
  `Pairable: yes` while the countdown runs.
- Put the host's Bluetooth settings into “add device” mode first, then start
  pairing on the CardputerZero.
- If the host previously paired an older build, it may cache the name and
  services: remove the device on the host, then pair again.
- Too many stale bonds in `/var/lib/bluetooth`: `bluetoothctl devices` and
  `bluetoothctl remove <MAC>` for entries you no longer use.

## Pairing fails or the host reports an authentication error

Check the agent and the daemon:

```bash
sudo journalctl -u bluetooth -n 100 --no-pager
python3 -c "import dbus, gi; print('ok')"
```

- `python3-gi` missing → the auto-accept agent cannot register. Install it and
  restart the app (the profile still works, but pairing may be refused).
- `No agent available` / `AuthenticationFailed` → restart Bluetooth, then
  retry: `sudo systemctl restart bluetooth`.
- Host and device disagree after a failed attempt: remove the bond on **both**
  sides, then re-pair.

## The host shows a keyboard, a joystick, or an unknown device

The SDP record advertises a mouse (`HIDDeviceSubclass 0x80`, device class
`0x0580`). If a host still shows something else, it cached an older record:

1. Remove the device on the host.
2. For extra certainty, change nothing but re-pair — hosts key the cache on the
   Bluetooth address, so removing on the host is what matters.
3. On Linux: `bluetoothctl info <MAC>` shows `Class` and the HID UUID.

## Connected, but the pointer does not move

- Is the state `RUNNING` (amber card, timer ticking, `N reports` increasing)?
- Slow mode sends one report every **30 seconds** — wait half a minute before
  concluding it is broken.
- Host side, Linux: `sudo libinput debug-events` should show
  `pointer motion` events. `dmesg | grep hid` should show a `hid-generic`
  binding.
- The host may ignore motion while the session is locked — this app does not
  (and should not) unlock anything.
- If reports increment but nothing moves, the host's HID stack rejected the
  descriptor: remove and re-pair.

## It disconnects after a while

- Host sleep/suspend drops the link; the app returns to `OFFLINE` and accepts a
  new connection automatically.
- Weak signal / 2.4 GHz congestion: keep the device close, and note that Wi-Fi
  and Bluetooth share the radio.
- `sudo journalctl -u bluetooth -n 100` shows the disconnect reason
  (`Connection timeout`, `Page timeout`, …).

## Screen stays black or looks wrong

```bash
cat /sys/class/graphics/fb*/name
```

`fb_st7789v` is the LCD. The app auto-detects it; override with
`--fb /dev/fb1`. If the panel shows garbled colours, the framebuffer is not
16 bpp RGB565 — report it with the output of
`fbset -i` / `cat /sys/class/graphics/fb0/bits_per_pixel`.

## Keys do nothing

```bash
ls /dev/input/by-path/
sudo evtest
```

The expected node is `/dev/input/by-path/platform-3f804000.i2c-event`. If your
image names it differently, pass `--keys /dev/input/eventN`. Without a
keyboard the app still runs and pairs, but the UI cannot be driven.

## Exit / relaunch problems

- A single ESC exits from the main screen; in the pairing page and the Rename
  editor it cancels/returns instead.
- If the app is killed, the HID profile can survive in `bluetoothd` until the
  next start (which unregisters it first). A stubborn case:
  `sudo systemctl restart bluetooth`.
- APPLaunch may send `SIGINT`; the app handles it and closes the link cleanly.

## Nothing works — collect this

```bash
bluetoothctl --version
bluetoothctl show
bluetoothctl devices
sudo journalctl -u bluetooth -n 200 --no-pager
cat /sys/class/graphics/fb*/name
sudo /usr/share/APPLaunch/bin/mouse-jiggler --debug
```
