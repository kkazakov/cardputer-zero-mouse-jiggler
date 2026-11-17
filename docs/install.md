# Install

## Prerequisites

- M5Stack **CardputerZero** (C154 / C155) running the stock CardputerZero OS.
- SSH or ADB access, and the `pi` user's password (or root).
- `python3-pil`, `python3-dbus`; `python3-gi` is needed for the pairing agent.

```bash
sudo apt update
sudo apt install python3-pil python3-dbus python3-gi
```

Check Bluetooth is alive before installing the app:

```bash
bluetoothctl show          # Powered: yes, AdapterAddress ...
rfkill list                # no soft block on hci0
```

## From a checkout

```bash
# on your workstation
scp -r cardputer-zero-mouse-emu pi@cardputerzero.local:~/

# on the device
cd ~/cardputer-zero-mouse-emu
sudo ./install.sh
```

### Bluetooth service fix (required)

BlueZ's `input` plugin implements the HID *device* role itself and keeps L2CAP
PSMs 0x11/0x13 bound, so the app fails with
`HID channels busy: ... bluetoothd holds PSMs 17/19`. On the tested image the
fix is:

```bash
sudo ./install.sh bluetooth-fix
```

It installs `/etc/systemd/system/bluetooth.service.d/mouse-jiggler.conf`:

```ini
[Service]
ExecStart=
ExecStart=/usr/libexec/bluetooth/bluetoothd -P input
```

Trade-off: the CardputerZero can no longer act as a Bluetooth HID **host**
(connecting a keyboard or mouse to it). Undo with
`sudo ./install.sh bluetooth-restore`. Re-run `bluetooth-fix` after a full OS
update that ships a new bluetooth.service, or after a factory reset.

`install.sh` performs exactly four copies into `/usr/share/APPLaunch`:

| Source | Destination |
| --- | --- |
| `src/mouse_jiggler/` | `share/mouse-jiggler/mouse_jiggler/` |
| `packaging/mouse-jiggler.sh` | `bin/mouse-jiggler` |
| `applaunch/applications/mouse-jiggler.desktop` | `applications/mouse-jiggler.desktop` |
| `applaunch/share/images/mouse-jiggler.png` | `share/images/mouse-jiggler.png` |

and then restarts APPLaunch — first as a system service, then as the desktop
user's `systemctl --user` service (the stock image uses the user service). If
neither is available, reboot the device to see the icon.

The launcher entry is:

```ini
[Desktop Entry]
Name=Mouse Jiggler
Comment=Bluetooth mouse jiggler (Slow / Fast / Jiggle)
Exec=bin/mouse-jiggler
Terminal=false
Icon=share/images/mouse-jiggler.png
Type=Application
```

Relative `Exec` and `Icon` paths resolve under `/usr/share/APPLaunch`.

## Debian package

`packaging/build-deb.sh` stages the same four paths as `install.sh` and wraps
them in a `.deb`.

### Build on the device (or any Debian/Ubuntu host with `dpkg-deb`)

```bash
cd ~/cardputer-zero-mouse-emu
./packaging/build-deb.sh
# -> dist/mouse-jiggler_0.2.2_arm64.deb
```

### Build anywhere with Docker

No Python or `dpkg-deb` needed on the host:

```bash
cd cardputer-zero-mouse-emu
rm -rf build dist
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/src" -w /src \
  ubuntu:24.04 ./packaging/build-deb.sh
```

### Install

```bash
sudo apt install ./dist/mouse-jiggler_0.2.2_arm64.deb
# APPLaunch only rescans applications when it starts:
#   system service:  sudo systemctl restart APPLaunch.service
#   user service:    systemctl --user restart APPLaunch.service
# or just reboot.
```

Inspect before installing:

```bash
dpkg-deb -I dist/mouse-jiggler_0.2.2_arm64.deb     # metadata, depends
dpkg-deb -c dist/mouse-jiggler_0.2.2_arm64.deb     # file list
```

The package is `Architecture: arm64` (matching platform conventions) even
though the code is pure Python. Depends: `python3`, `python3-pil`,
`python3-dbus`, `python3-gi`, `bluez`. It installs:

```
/usr/share/APPLaunch/applications/mouse-jiggler.desktop
/usr/share/APPLaunch/bin/mouse-jiggler
/usr/share/APPLaunch/share/images/mouse-jiggler.png
/usr/share/APPLaunch/share/mouse-jiggler/mouse_jiggler/...
```

Remove with `sudo apt remove mouse-jiggler`. The Bluetooth drop-in from
`bluetooth-fix` is *not* part of the package (it changes system services);
run it once with `sudo ./install.sh bluetooth-fix`.

## Running without the launcher

Useful while debugging; the app needs root for the L2CAP PSMs.

```bash
sudo PYTHONPATH=/usr/share/APPLaunch/share/mouse-jiggler \
     python3 -m mouse_jiggler --debug
```

or through the installed wrapper:

```bash
sudo /usr/share/APPLaunch/bin/mouse-jiggler --debug
```

Options:

```
--fb PATH            framebuffer device (default: auto-detect ST7789V)
--keys PATH          input event device (default: auto)
--adapter NAME       Bluetooth adapter (default: hci0)
--config PATH        config file (default: ~/.config/mouse-jiggler/config.json)
--pairing-seconds N  pairing window (default: 180)
--exit-hold N        ESC hold time (default: 3)
--debug              verbose logs
```

If the app dies before releasing the HID profile, the next start unregisters the
stale record automatically.

## Uninstall

```bash
sudo ./install.sh uninstall
sudo systemctl restart APPLaunch.service
```

or `sudo apt remove mouse-jiggler` for the `.deb`.

## Runtime permissions

`/usr/share/APPLaunch` apps run as root, which is what binding L2CAP PSMs 0x11
and 0x13 requires. There is no capability-only mode in this release; running
manually therefore needs `sudo`.

## Where state lives

| Path | Contents |
| --- | --- |
| `/root/.config/mouse-jiggler/config.json` | selected mode, last bonded host |
| `/var/lib/bluetooth/...` | BlueZ bond keys (managed by BlueZ) |
| journal / console | app logs (`--debug` for detail) |
