#!/usr/bin/env bash
# Build an installable .deb from the working tree.
#   ./packaging/build-deb.sh [version]
# Output: dist/mouse-jiggler_<version>_arm64.deb
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$SRC/src/mouse_jiggler/__init__.py")}"
STAGE="$SRC/build/deb"
OUT="$SRC/dist"
PKG="mouse-jiggler"

rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/share/APPLaunch"

# Cross-compile the capability launcher for the device.
CAPLAUNCH="$STAGE/usr/lib/mouse-jiggler/caplaunch"
CC_BIN=""
for candidate in aarch64-linux-gnu-gcc aarch64-unknown-linux-gnu-gcc; do
  if command -v "$candidate" >/dev/null 2>&1; then CC_BIN="$candidate"; break; fi
done
mkdir -p "$(dirname "$CAPLAUNCH")"
if [ -n "$CC_BIN" ]; then
  "$CC_BIN" -O2 -Wall -o "$CAPLAUNCH" "$SRC/packaging/caplaunch.c"
  strip "$CAPLAUNCH" 2>/dev/null || true
  echo "built capability launcher with $CC_BIN"
else
  echo "warning: no aarch64 cross compiler; the package will fall back to sudo" >&2
fi

APP_ROOT="$STAGE/usr/share/APPLaunch" SKIP_RESTART=1 SKIP_DEPS=1 SKIP_CAPLAUNCH=1 \
  "$SRC/install.sh" install

# postinst grants the file capability the launcher needs
if [ -f "$CAPLAUNCH" ]; then
  mkdir -p "$STAGE/DEBIAN"
  cat > "$STAGE/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
if command -v setcap >/dev/null 2>&1; then
    setcap cap_net_bind_service=pie /usr/lib/mouse-jiggler/caplaunch || true
fi
exit 0
POSTINST
  chmod 755 "$STAGE/DEBIAN/postinst"
fi

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
