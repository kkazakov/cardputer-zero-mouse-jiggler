# AGENTS.md

## 1. Project Overview

**Mouse Jiggler** is a Python 3.10+ app for the M5Stack CardputerZero (aarch64
Linux, 320×170 framebuffer) that presents the device as a **classic Bluetooth
HID mouse** and nudges the host pointer in three modes. The transport is built
directly on BlueZ (HID profile + raw L2CAP), not on a GUI toolkit or a daemon.

Your role: maintain the app and its pixel UI, keep tests green, and treat the
on-device Bluetooth path as **unverified** until the M0 spike passes
(`docs/protocol.md`). Call the project **Mouse Jiggler** in prose.

## 2. Commands

```bash
python3 -m pytest tests -q                                   # full suite, no hardware
python3 -m pytest tests/test_app.py::test_start_stop_and_zero_report -q   # one test
ruff check src tests tools                                  # lint (config: pyproject.toml)

python3 tools/render_assets.py                              # regenerate docs/ui-*.png + icon
PYTHONPATH=src python3 -m mouse_jiggler --help              # CLI smoke test
APP_ROOT=/tmp/czroot SKIP_RESTART=1 ./install.sh install    # stage the launcher layout
./packaging/build-deb.sh                                    # dist/*.deb (needs dpkg-deb)
```

## 3. Architecture

| Path | Purpose |
| --- | --- |
| `src/mouse_jiggler/app.py` | state machine, timers, keys, render dispatch — **no I/O** |
| `state.py` / `config.py` / `modes.py` | states, persisted JSON prefs (mode, host, device name), mode table |
| `hid/` | report descriptor, 4-byte reports, motion vectors (pure) |
| `bt/` | SDP XML, BlueZ profile, pairing agent, L2CAP/HIDP server, transport facade |
| `platform/fb.py` | ST7789V framebuffer discovery, ioctl, mmap, RGB565 |
| `input/keypad.py` | raw evdev reader for the tca8418 keypad (no python-evdev) |
| `input/text.py` | name editor: keymap, shift, select-all, 20-char limit |
| `ui/` | tokens, DejaVu loading, icons, screen composition, launcher icon |
| `tests/support.py` | fakes: clock, transport, display, keypad |

`App` depends on interfaces (`transport`, `display`, `keypad`, `clock`), never on
concrete classes. Keep it constructible with fakes; it must not read the clock
or sleep directly.

## 4. Conventions

- Compose screens in `ui/screens.py` from `ui/theme.py` tokens; never hardcode
  colors or geometry elsewhere. A 1 px border = outer rounded rect in the border
  color + inset fill at `+1 px / radius-1`.
- `hid/descriptor.py:REPORT_ID = 2` is part of the wire format. The SDP record
  injects `DESCRIPTOR_HEX`; change one, update the other, the golden tests and
  `docs/protocol.md`.
- Drive the app with a fake clock and transport:

```python
def test_feature(env):
    app, transport, display, keypad, clock, config = env
    press(app, KEY_ENTER)          # helper in tests/test_app.py
    transport.connect()
    app.step()
    assert app.state is State.CONNECTED
```

Use `clock.advance(30)` + `app.step()`; never `time.sleep`.

- User-facing errors are one short line (fits 320 px) and raise
  `TransportError`, `BluezError`, `HidServerError` or `FramebufferError`.

## 5. Boundaries

**NEVER**

- Hardcode `/dev/fb0`; the LCD is usually `/dev/fb1`. Use `platform.fb.find_device()`.
- Change `REPORT_ID`, descriptor bytes or the SDP UUID without updating tests and
  `docs/protocol.md` in the same change.
- Call `time.sleep` / `time.monotonic` inside `App` — inject the clock.
- Reintroduce a hold-to-exit overlay: `ESC` is a plain press/release now.
- Commit real MAC addresses, host names, or a device's `config.json`.
- Add a dependency without updating README requirements and the `.deb` `Depends:`.
- Submit to the App Store: the app needs root, which the store forbids.

**REQUIRE HUMAN CONFIRMATION**

- Changing the SDP record, device class or HID profile path (pairing behaviour).
- Running `unpair()` or writing to `/usr/share/APPLaunch` on a real device.
- Bumping `__version__`, building/publishing a `.deb`, or force-pushing.

## 6. Gotchas

- **BlueZ keeps the HID profile after a crash.** `register_profile()` unregisters
  first on purpose — do not remove that.
- **L2CAP PSMs 17/19 need root and must be free**: bluetoothd's `input` plugin
  holds them, so `install.sh bluetooth-fix` (`-P input`) is required. APPLaunch
  runs apps as the user; the wrapper re-execs through `sudo -n`.
- **`transport.poll(0.02)` blocks** and needs real sockets. Never use
  `BluetoothTransport` in tests; use `FakeTransport`.
- **Pairing needs the GLib D-Bus loop** (`python3-gi`); without it the profile
  registers but the auto-accept agent cannot answer.
- **Config path follows the user** (`/root/.config/...` under APPLaunch), and the
  marketing photo is cyan-shifted — the real palette is mint `#88f0b3`.
