#!/usr/bin/env bash
# Build an installable .deb from the working tree.
#   ./packaging/build-deb.sh [version]
# Output: dist/mouse-jiggler_<version>_arm64.deb
#
# The package must ship the capability launcher: without it the app falls back
# to sudo -n, i.e. root, which is exactly what the store forbids. So a missing
# aarch64 compiler is an error, not a warning. Override with
# ALLOW_MISSING_CAPLAUNCH=1 only for a local try.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$SRC/src/mouse_jiggler/__init__.py")}"
STAGE="$SRC/build/deb"
OUT="$SRC/dist"
PKG="mouse-jiggler"

rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/share/APPLaunch"

# Build the capability launcher. On an aarch64 host the native compiler is
# enough; otherwise a cross compiler is required. A static binary avoids
# depending on the device's glibc version (the loader would otherwise fail with
# "GLIBC_2.xx not found", which looks nothing like a capability problem).
CAPLAUNCH="$STAGE/usr/lib/mouse-jiggler/caplaunch"
CC_BIN=""
HOST_ARCH="$(uname -m)"
case "$HOST_ARCH" in
  aarch64|arm64) CANDIDATES="cc gcc" ;;
  *)             CANDIDATES="aarch64-linux-gnu-gcc aarch64-unknown-linux-gnu-gcc" ;;
esac
for candidate in $CANDIDATES; do
  if command -v "$candidate" >/dev/null 2>&1; then CC_BIN="$candidate"; break; fi
done
mkdir -p "$(dirname "$CAPLAUNCH")"
if [ -z "$CC_BIN" ]; then
  if [ "${ALLOW_MISSING_CAPLAUNCH:-0}" = "1" ]; then
    echo "warning: no aarch64 compiler; building a package that runs as root" >&2
  else
    cat >&2 <<'MSG'
error: no aarch64 C compiler, so the capability launcher cannot be built.
       Install one of:
         Debian/Ubuntu   sudo apt install gcc-aarch64-linux-gnu
         Arch/CachyOS    sudo pacman -S aarch64-linux-gnu-gcc
       or build inside the container image from docs/install.md.
       Without the launcher the app runs as root through sudo -n.
MSG
    exit 1
  fi
else
  # A native aarch64 build links against the device's own glibc. A cross build
  # links statically, otherwise the loader can fail on the device with
  # "GLIBC_2.xx not found" — which looks nothing like a capability problem.
  LINK_FLAGS=""
  [ "$HOST_ARCH" != "aarch64" ] && [ "$HOST_ARCH" != "arm64" ] && LINK_FLAGS="-static"
  if ! "$CC_BIN" -O2 -Wall $LINK_FLAGS -o "$CAPLAUNCH" "$SRC/packaging/caplaunch.c"; then
    if [ -n "$LINK_FLAGS" ] \
       && "$CC_BIN" -O2 -Wall -o "$CAPLAUNCH" "$SRC/packaging/caplaunch.c"; then
      echo "warning: static link failed; launcher is dynamic and needs a glibc no" >&2
      echo "         newer than the device's (Debian 13 trixie ships 2.41)" >&2
    else
      echo "error: could not build the capability launcher" >&2
      exit 1
    fi
  fi
  strip "$CAPLAUNCH" 2>/dev/null || true
  chmod 755 "$CAPLAUNCH"          # umask 002 would leave it group-writable
  echo "built capability launcher with $CC_BIN${LINK_FLAGS:+ ($LINK_FLAGS)}"
fi

if [ -f "$CAPLAUNCH" ] && command -v file >/dev/null 2>&1 \
   && ! file -b "$CAPLAUNCH" | grep -q 'ARM aarch64'; then
  echo "error: $CAPLAUNCH is not an aarch64 binary: $(file -b "$CAPLAUNCH")" >&2
  exit 1
fi

APP_ROOT="$STAGE/usr/share/APPLaunch" SKIP_RESTART=1 SKIP_DEPS=1 SKIP_CAPLAUNCH=1 \
  "$SRC/install.sh" install

# postinst grants the file capability the launcher needs and verifies it stuck
mkdir -p "$STAGE/DEBIAN"
cat > "$STAGE/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
LAUNCHER=/usr/lib/mouse-jiggler/caplaunch
if [ ! -x "$LAUNCHER" ]; then
    echo "mouse-jiggler: capability launcher missing ($LAUNCHER)" >&2
    exit 0
fi
if command -v setcap >/dev/null 2>&1 && setcap cap_net_bind_service=pie "$LAUNCHER"; then
    if command -v getcap >/dev/null 2>&1 \
       && getcap "$LAUNCHER" | grep -q cap_net_bind_service; then
        echo "mouse-jiggler: runs as the desktop user (CAP_NET_BIND_SERVICE only)"
        exit 0
    fi
fi
echo "mouse-jiggler: WARNING could not grant CAP_NET_BIND_SERVICE to $LAUNCHER" >&2
echo "mouse-jiggler: the app will fall back to sudo -n (root);" >&2
echo "mouse-jiggler: check with 'sudo install.sh doctor' from the source tree" >&2
exit 0
POSTINST
chmod 755 "$STAGE/DEBIAN/postinst"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Architecture: arm64
Maintainer: Krasimir Kazakov <kkazakov@gmail.com>
Section: utils
Priority: optional
Depends: python3, python3-pil, python3-dbus, python3-gi, bluez, libcap2-bin
Description: Bluetooth mouse jiggler for the M5Stack CardputerZero
 A classic Bluetooth HID mouse that nudges the host pointer in three
 selectable rhythms (Slow, Fast, Jiggle). Runs from APPLaunch.
EOF

mkdir -p "$OUT"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT/${PKG}_${VERSION}_arm64.deb"
echo "built $OUT/${PKG}_${VERSION}_arm64.deb"
