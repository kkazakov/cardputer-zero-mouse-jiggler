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

APP_ROOT="$STAGE/usr/share/APPLaunch" SKIP_RESTART=1 "$SRC/install.sh" install

cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Architecture: arm64
Maintainer: CardputerZero Mouse Jiggler
Section: utils
Priority: optional
Depends: python3, python3-pil, python3-dbus, python3-gi, bluez
Description: Bluetooth mouse jiggler for the M5Stack CardputerZero
 A classic Bluetooth HID mouse that nudges the host pointer in three
 selectable rhythms (Slow, Fast, Jiggle). Runs from APPLaunch.
EOF

mkdir -p "$OUT"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT/${PKG}_${VERSION}_arm64.deb"
echo "built $OUT/${PKG}_${VERSION}_arm64.deb"
