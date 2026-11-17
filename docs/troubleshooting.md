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

## “binding L2CAP PSMs needs root”

The app is not running as root. APPLaunch launches apps as root, so this only
happens with a manual run — use `sudo`. The capability cannot be granted
per-file to a Python entry point.

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
