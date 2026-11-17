# Changelog

## 0.2.7 — 2026-11-17

- **The `.deb` shipped without the capability launcher.** `build-deb.sh` only
  built it when an `aarch64-linux-gnu-gcc` happened to be installed, and still
  produced a package otherwise: 0.2.6 contains an empty
  `/usr/lib/mouse-jiggler/`, no `postinst` and therefore no `setcap`, so the
  wrapper fell back to `sudo -n`, i.e. root. The build now fails without a
  cross compiler, links the launcher statically, checks that it really is
  aarch64, and the `postinst` verifies the grant with `getcap`.
- `caplaunch` no longer continues silently when it cannot raise
  `CAP_NET_BIND_SERVICE`: it says why on stderr and exits 77, and
  `bin/mouse-jiggler` treats 77 as "fall back to `sudo -n`" instead of a dead
  end. `install.sh` verifies `setcap` with `getcap` before believing it, and
  warns when the filesystem drops file capabilities.
- New `./install.sh doctor` (`tools/doctor.sh`): proves end to end that the
  capability reaches Python and that PSM 19 can be bound — without root and
  without starting the app.
- The error page hint no longer says "run as root" (the store forbids it), and
  the stale "the app runs as root" claims are gone from README and `server.py`.
- `./install.sh doctor` now also reports file capabilities on the interpreter.
  That was the actual device failure: `/usr/bin/python3.13` carried
  `cap_net_raw=eip`, and the kernel zeroes the *ambient* set when `execve()`
  runs a privileged file, so Python received `CAP_NET_RAW` instead of
  `CAP_NET_BIND_SERVICE` (`CapEff 0x2000`, `CapAmb 0`) and the HID bind was
  denied. Capability removed; the app runs as uid 1000 with `CapEff 0x400` and
  binds PSM 0x11/0x13.
- `install.sh` resolves `setcap`/`getcap` in `/usr/sbin`, so a non-root install
  on Debian no longer reports "setcap not found" and skips the grant.
- 83 tests.

## 0.2.6 — 2026-11-17

- Fixed a SIGSEGV when the Bluetooth setup failed (e.g. a second instance while
  the first holds the HID PSMs): the D-Bus/GLib threads were still running while
  dbus-python finalised its objects. The main loop is now stopped during
  shutdown and the process exits without interpreter teardown.
- The error page no longer flashes and disappears: it stays on screen, `OK`
  retries the Bluetooth setup, `ESC` leaves the app.
- 81 tests.

## 0.2.5 — 2026-11-17

- Launcher icon: dropped the baked-in tile border. APPLaunch draws its own grey
  frame around every icon, so the outline appeared as a doubled border.
  Artwork (plate, pointer, trails, badge) unchanged.

## 0.2.4 — 2026-11-17

- Added `app-builder.json` (czdev / App Store manifest) plus
  `store/screenshots/` (four 320×170 states) and `docs/publish.md`.
- **The app no longer needs root.** `packaging/caplaunch.c` is a 3 KB launcher
  carrying `CAP_NET_BIND_SERVICE`, installed with `setcap` by `install.sh` and by
  the package `postinst`. Verified on the device: `Uid 1000`,
  `CapEff 0x400`. The wrapper falls back to `sudo -n` when the launcher is
  unavailable.
- `.deb` gains `libcap2-bin` as a dependency and a `postinst`.
- 80 tests.

## 0.2.3 — 2026-11-17

- Launcher icon: the tile border is now the launcher's grey `#414441` instead
  of mint, so the icon sits in the home screen's grey frame like every other
  app. Artwork unchanged.

## 0.2.2 — 2026-11-17

- Removed the "hold ESC" popup entirely; `ESC` is a single press everywhere.
  There is no hold timer and no exit overlay any more.
- `packaging/build-deb.sh` now builds cleanly in a container (`SKIP_DEPS=1`)
  and normalises file modes to 644/755 inside the package.

## 0.2.1 — 2026-11-17

- A single `ESC` now exits the app from the main screen (and still cancels
  pairing / leaves Rename and re-pair pages). The 3 s hold remains as a fallback.
- Home footer hint changed from `ESC Hold 3s` to `ESC Exit`.
- 86 tests.

## 0.2.0 — 2026-11-17

- New **Rename** card: edit the Bluetooth device name on the keyboard. Typing
  replaces the prefilled name, 20-character limit, `OK` saves, `ESC` cancels.
- The name is persisted in `config.json`, written to the adapter alias and
  re-registered in the SDP record, so hosts discover the new name immediately.
- Startup now forces `Pairable`/`Discoverable` off, cleaning up after a crash
  that happened mid-pairing.
- 80 tests (name editor, rename flow, config sanitising, UI).

## 0.1.1 — 2026-11-16

- Verified end-to-end on a real CardputerZero against a Linux host: pairing,
  HID enumeration and `REL_X` motion events (docs/hardware-verification.md).
- Fixed `fb_var_screeninfo.bits_per_pixel` parsing (offset 24, not the third
  u32) — the panel reports 16 bpp, the old code read 320.
- Added `install.sh bluetooth-fix` / `bluetooth-restore`: BlueZ's `input`
  plugin holds PSMs 0x11/0x13, so bluetoothd must run with `-P input`.
- Launcher wrapper re-execs through `sudo -n` (APPLaunch runs apps as the user).
- `install.sh` restarts the APPLaunch user service as well as the system one.
- Clearer "HID channels busy" error message.

## 0.1.0 — 2026-11-16

First implementation.

- Classic Bluetooth HID mouse transport: BlueZ `ProfileManager1` + SDP record,
  L2CAP PSM 0x11/0x13, HIDP control replies, 4-byte input reports (report ID 2).
- Three motion modes: Slow (2 px / 30 s), Fast (5 px / 10 s),
  Jiggle (20–30 px / 100 ms), with alternating vectors so drift stays bounded.
- Carousel UI cloned from Ultimate-Remote's CardputerZero renderer: 320×170,
  Pair / Start-Stop / Mode cards, status badge, dots, hint bar.
- Pairing: 180 s discoverable window, `NoInputNoOutput` agent, re-pair and
  forget confirmation, bond persistence through BlueZ.
- Exit: 3 s ESC hold with progress overlay, SIGINT/SIGTERM clean shutdown,
  zero report on stop.
- Raw evdev keypad reader (no python-evdev dependency), framebuffer detection
  for the ST7789V panel (`/dev/fb1` on most images).
- APPLaunch packaging: `.desktop`, icon, `install.sh`, `packaging/build-deb.sh`.
- 69 unit/state-machine tests with fake clock, transport, display and keypad.
