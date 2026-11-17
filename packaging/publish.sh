#!/usr/bin/env bash
# Publish this app to the CardputerZero App Store with czdev.
#
# czdev needs `git` and `dpkg-deb` on the machine that runs it. On a Debian or
# Ubuntu host those are usually present; on Arch/CachyOS install the `dpkg`
# package. If neither is available, this wrapper runs czdev inside a throwaway
# container instead, so nothing has to be installed on the host.
#
#   ./packaging/publish.sh                      # publishes ./dist/*.deb
#   ./packaging/publish.sh --deb path/to.deb
#   CZDEV_DIR=~/Projects/CardputerZero-AppBuilder ./packaging/publish.sh
#
# The GitHub token from `czdev login` (~/.czdev/credentials) is mounted into the
# container; it is never copied into the image.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CZDEV_DIR="${CZDEV_DIR:-}"
CREDENTIALS="${HOME}/.czdev"

find_czdev() {
  if [ -n "$CZDEV_DIR" ] && [ -x "$CZDEV_DIR/czdev" ]; then
    printf '%s\n' "$CZDEV_DIR/czdev"
    return 0
  fi
  for candidate in \
    "$SRC/../CardputerZero-AppBuilder/czdev" \
    "$SRC/../AppBuilder/czdev" \
    "$HOME/Projects/CardputerZero-AppBuilder/czdev" \
    "$HOME/AppBuilder/czdev"; do
    if [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

CZDEV="$(find_czdev || true)"
if [ -z "$CZDEV" ]; then
  cat >&2 <<'EOF'
czdev was not found. Clone it once:

  git clone https://github.com/CardputerZero/AppBuilder ~/Projects/CardputerZero-AppBuilder
  ~/Projects/CardputerZero-AppBuilder/czdev login

Then re-run this script (or point CZDEV_DIR at the checkout).
EOF
  exit 1
fi

if [ ! -f "$CREDENTIALS/credentials" ]; then
  echo "Not logged in. Run first:  $CZDEV login" >&2
  exit 1
fi

# Native path: everything czdev needs is already installed.
if command -v dpkg-deb >/dev/null 2>&1 && command -v git >/dev/null 2>&1; then
  exec "$CZDEV" publish "$@"
fi

# Container path: same command, throwaway Ubuntu with dpkg + git.
if ! command -v docker >/dev/null 2>&1; then
  cat >&2 <<'EOF'
czdev needs `dpkg-deb`, which is not installed, and docker is not available either.

Install it and re-run:
  Arch / CachyOS:  sudo pacman -S dpkg
  Debian / Ubuntu: sudo apt install dpkg-dev
EOF
  exit 1
fi

echo "dpkg-deb not found on the host: running czdev inside a container." >&2
exec docker run --rm -i \
  -v "$SRC:/src" \
  -v "$(dirname "$CZDEV"):/czdev-src:ro" \
  -v "$CREDENTIALS:/root/.czdev:ro" \
  -w /src \
  ubuntu:24.04 \
  bash -lc 'apt-get update -qq >/dev/null 2>&1 &&
           apt-get install -y -qq dpkg-dev git python3 ca-certificates >/dev/null 2>&1 &&
           exec /czdev-src/czdev publish "$@"' _ "$@"
