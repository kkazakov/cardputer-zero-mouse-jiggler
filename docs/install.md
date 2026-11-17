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

Useful while debugging. `python3 -m mouse_jiggler` alone gets no capability,
so this needs `sudo`, or the installed wrapper (which goes through the
capability launcher):

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

Binding L2CAP PSMs 0x11/0x13 (HID control/interrupt) needs
`CAP_NET_BIND_SERVICE`. The installer prefers a helper that carries exactly
that capability instead of running the app as root:

| Piece | Purpose |
| --- | --- |
| `/usr/lib/mouse-jiggler/caplaunch` | tiny launcher, file capability `cap_net_bind_service=pie`, raises it into the ambient set and execs `python3 -m mouse_jiggler` |
| `setcap` in `postinst` (deb) / `install.sh` | grants the capability at install time |
| `/usr/share/APPLaunch/bin/mouse-jiggler` | wrapper: caplaunch → root → `sudo -n`, in that order |

`install.sh` compiles `packaging/caplaunch.c` with whatever compiler is present
(`gcc`, `cc` or `aarch64-linux-gnu-gcc`) and runs `setcap`, which comes from
`libcap2-bin`. A grant is only trusted after `getcap` confirms it stuck: a
`nosuid` or read-only filesystem silently drops file capabilities, so the
installer says so instead of claiming success.

### Verify it

```bash
./install.sh doctor
```

Run it as the app's user (on the stock image `pi`). As root it re-runs itself as
`$SUDO_USER`, because root holds the capability by definition and would make the
probe meaningless.

The doctor reports the launch chain step by step and exits non-zero when the
non-root path is broken. It proves the important part directly: it runs the
launcher with a `sitecustomize` that prints the capabilities Python received
and binds PSM 19:

```text
== probe: what python3 receives through the launcher ==
  caps    Uid:     1000    1000    1000    1000
  caps    CapEff:  0000000000000400
  caps    CapAmb:  0000000000000400
  ok      bound PSM 19 — the capability reaches python3
```

The equivalent by hand, against a running app:

```bash
/usr/share/APPLaunch/bin/mouse-jiggler &
grep -E '^Uid|^CapEff' /proc/$(pgrep -f 'mouse_jiggler$' | head -1)/status
# Uid: 1000 ...   CapEff: 0000000000000400   (CAP_NET_BIND_SERVICE only)
getcap /usr/lib/mouse-jiggler/caplaunch
# /usr/lib/mouse-jiggler/caplaunch cap_net_bind_service=eip   (p, i, e as set)
```

The doctor also inspects the interpreter: a file capability on
`/usr/bin/python3` (left over from testing raw sockets, say) defeats the
handoff — `execve()` zeroes the ambient set for a privileged file, so Python
gets `CAP_NET_RAW` and not `CAP_NET_BIND_SERVICE`, and the app reports
`binding L2CAP PSMs needs CAP_NET_BIND_SERVICE`. Remove it with
`sudo setcap -r /usr/bin/python3.13`.

### When the capability cannot be granted

`caplaunch` exits with status **77** when it cannot raise
`CAP_NET_BIND_SERVICE` (no file capability, `nosuid` mount, hardened
`no_new_privs`) and says why on stderr. `bin/mouse-jiggler` matches that status
and re-execs through `sudo -n`, so the app still starts — as root. The on-screen
error `binding L2CAP PSMs needs CAP_NET_BIND_SERVICE` means neither path got the
privilege: run the doctor.

A manual `sudo python3 -m mouse_jiggler` still works for debugging.

## Where state lives

| Path | Contents |
| --- | --- |
| `/root/.config/mouse-jiggler/config.json` | selected mode, last bonded host |
| `/var/lib/bluetooth/...` | BlueZ bond keys (managed by BlueZ) |
| journal / console | app logs (`--debug` for detail) |
