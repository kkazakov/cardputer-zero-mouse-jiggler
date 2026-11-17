# Publishing to the CardputerZero App Store

The repo carries an [`app-builder.json`](../app-builder.json) manifest for
[czdev](https://github.com/CardputerZero/AppBuilder), the CLI the store uses to
build and publish `.deb` packages.

## Manifest

```jsonc
{
  "package_name": "mouse-jiggler",
  "version": "0.2.3",
  "app_name": "Mouse Jiggler",
  "bin_name": "mouse-jiggler",
  "store": { "summary": "...", "categories": ["System Tools"], "screenshots": [...],
             "icon": "assets/icon-256.png", "license": "MIT", "share_code": "MOUS", ... }
}
```

| Field | Value | Notes |
| --- | --- | --- |
| `package_name` | `mouse-jiggler` | stable Debian id, cannot change after first publish |
| `app_name` | `Mouse Jiggler` | store title, must be unique store-wide |
| `store.share_code` | `MOUS` | 4 characters, checked against the live registry when chosen |
| `store.categories` | `System Tools` | from the fixed enum |
| `store.icon` | `assets/icon-256.png` | 256×256 square PNG |
| `store.screenshots` | `store/screenshots/0*.png` | exactly 320×170, four distinct states |
| `store.permissions` | all `false` | no camera, mic, IMU, network, extra hardware |

Regenerate the screenshots from the app's own renderer whenever the UI changes:

```python
import sys; sys.path.insert(0, "src")
from mouse_jiggler.ui import screens
screens.render_home(screens.HomeState(selected=1)).save("store/screenshots/01-home.png")
```

## Preflight

The store runs `prepublish_check.py` from the
[CardputerZero skill repo](https://github.com/CardputerZero/skill) before
anything is uploaded. Run the same check locally:

```bash
curl -sLO https://raw.githubusercontent.com/CardputerZero/skill/main/cardputer-app-publish/scripts/prepublish_check.py
./packaging/build-deb.sh
python3 prepublish_check.py --deb dist/mouse-jiggler_0.2.7_arm64.deb --app-dir .
# Prepublish check passed.
```

`build-deb.sh` cross-compiles `packaging/caplaunch.c` for aarch64 and **refuses**
to build without a cross compiler (`gcc-aarch64-linux-gnu` on Debian/Ubuntu,
`aarch64-linux-gnu-gcc` on Arch/CachyOS; or build on the device itself). That
launcher is what keeps the app off root — a package built without it falls back
to `sudo -n` and would fail the store's no-root rule.

## Publishing with czdev

```bash
git clone https://github.com/CardputerZero/AppBuilder ~/Projects/CardputerZero-AppBuilder
~/Projects/CardputerZero-AppBuilder/czdev login      # GitHub device flow, once

cd /path/to/cardputer-zero-mouse-emu
~/Projects/CardputerZero-AppBuilder/czdev publish --deb dist/mouse-jiggler_0.2.7_arm64.deb
```

### czdev needs `dpkg-deb`

`dpkg-deb` is not part of a default Arch/CachyOS install and czdev aborts with
`ERROR: dpkg-deb not found`. Either install it:

```bash
sudo pacman -S dpkg          # Arch / CachyOS  (package: dpkg 1.23.x)
sudo apt install dpkg-dev    # Debian / Ubuntu
```

…or let the wrapper do it in a container, which needs no system change:

```bash
./packaging/publish.sh --deb dist/mouse-jiggler_0.2.7_arm64.deb
```

`packaging/publish.sh` finds the czdev checkout (`CZDEV_DIR`, `../AppBuilder`,
`~/Projects/CardputerZero-AppBuilder`, …), requires an existing
`~/.czdev/credentials`, and either execs czdev natively or runs it in a
throwaway `ubuntu:24.04` with `dpkg-dev`, `git` and `python3`, mounting the repo
and the token read-only. The token is never copied into an image.

### What publish does

1. Preflight: `.desktop` present, no root systemd services, manifest fields,
   320×170 screenshots, square icon, `arm64` architecture.
2. Uploads the `.deb` to a `czdev-buffer` release in your fork of `packages`.
3. Opens a pull request against `CardputerZero/packages` with the metadata and a
   release manifest (sha256). CI re-validates and a maintainer merges.
4. First release of a new package is reviewed by hand: post a short video of the
   app running on the device in the PR.

`czdev publish` validates the manifest, uploads the `.deb` to a release in your
own fork and opens a pull request against the `packages` repo. A first-time
submission of a new package is reviewed by hand: post a short video of the app
running on the device in the PR. Later versions merge automatically.

The web portal (<https://dev.cardputer.cc/#/upload>) does the same thing
interactively.

## Store policy notes

- **Root is not allowed.** The package ships
  `/usr/lib/mouse-jiggler/caplaunch`, a small static launcher carrying only
  `CAP_NET_BIND_SERVICE`; `postinst` calls `setcap` on it and checks the grant
  with `getcap`. The app therefore runs as the desktop user with one
  capability, not as root. Verify with:

  ```bash
  /usr/share/APPLaunch/bin/mouse-jiggler &        # then
  grep -E '^Uid|^CapEff' /proc/<pid>/status       # Uid 1000, CapEff 0x400
  ```

- Bluetooth pairing needs no extra permission: it happens inside BlueZ.
- The app stores nothing outside `~/.config/mouse-jiggler/config.json`.

## Version bumps

`version` lives in three places: `app-builder.json`,
`src/mouse_jiggler/__init__.py` and `pyproject.toml`. Bump all three, rebuild,
then publish.
