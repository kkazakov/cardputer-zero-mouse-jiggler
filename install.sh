#!/usr/bin/env bash
# Install (or remove) Mouse Jiggler in APPLaunch.
# Run on the CardputerZero. Root is needed to write /usr/share and /usr/lib;
# the installed app then runs as the desktop user (capability launcher) or,
# as a fallback, through sudo -n.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="${APP_ROOT:-/usr/share/APPLaunch}"
CAPLAUNCH="${CAPLAUNCH:-/usr/lib/mouse-jiggler/caplaunch}"
SKIP_RESTART="${SKIP_RESTART:-0}"
SUDO=""
if [ "$(id -u)" -ne 0 ] && [ ! -w "$(dirname "$APP_ROOT")" ] && [ ! -w "$APP_ROOT" ]; then
  SUDO="sudo"
fi

ACTION="${1:-install}"

# Debian keeps setcap/getcap in /usr/sbin, which is not on a desktop user's
# PATH — that is how a normal `./install.sh` used to skip setcap and leave the
# launcher without its capability.
find_tool() {
  local tool="$1" dir
  if command -v "$tool" >/dev/null 2>&1; then command -v "$tool"; return 0; fi
  for dir in /usr/sbin /sbin /usr/bin /bin; do
    if [ -x "$dir/$tool" ]; then echo "$dir/$tool"; return 0; fi
  done
  return 1
}

# True when the file carries CAP_NET_BIND_SERVICE as a file capability.
# `setcap` can succeed without it sticking (nosuid/read-only filesystem, no
# xattr support), so every grant is verified instead of trusted.
has_file_cap() {
  local file="$1"
  if command -v getcap >/dev/null 2>&1 \
     && getcap "$file" 2>/dev/null | grep -q cap_net_bind_service; then
    return 0
  fi
  python3 - "$file" <<'PY' 2>/dev/null
import os
import struct
import sys

try:
    raw = os.getxattr(sys.argv[1], "security.capability")
except OSError:
    raise SystemExit(1)
perm, inh = struct.unpack_from("<II", raw, 4)
raise SystemExit(0 if (perm | inh) & (1 << 10) else 1)  # CAP_NET_BIND_SERVICE
PY
}

# Build the capability launcher if a compiler is available. Without it the app
# still works, but every launch goes through sudo -n (root).
build_caplaunch() {
  local compiler=""
  for candidate in gcc cc aarch64-linux-gnu-gcc; do
    if command -v "$candidate" >/dev/null 2>&1; then compiler="$candidate"; break; fi
  done
  if [ -z "$compiler" ]; then
    echo "no C compiler found: cannot build the capability launcher" >&2
    echo "  -> the app will run as ROOT through sudo -n instead of as your user" >&2
    echo "  -> for the non-root path: sudo apt install gcc && sudo $0 install" >&2
    return 0
  fi
  local tmp
  tmp="$(mktemp -d)"
  if ! "$compiler" -O2 -Wall -o "$tmp/caplaunch" "$SRC/packaging/caplaunch.c"; then
    echo "warning: could not build caplaunch" >&2
    rm -rf "$tmp"
    return 0
  fi
  $SUDO install -d "$(dirname "$CAPLAUNCH")"
  $SUDO install -m 755 "$tmp/caplaunch" "$CAPLAUNCH"
  rm -rf "$tmp"
  local setcap_bin=""
  if ! setcap_bin=$(find_tool setcap); then
    echo "warning: setcap not found (install libcap2-bin); the app will fall back to sudo" >&2
    return 0
  fi
  if $SUDO "$setcap_bin" cap_net_bind_service=pie "$CAPLAUNCH" && has_file_cap "$CAPLAUNCH"; then
    echo "capability launcher installed (runs as the desktop user, no root)"
    return 0
  fi
  echo "warning: CAP_NET_BIND_SERVICE did not stick on $CAPLAUNCH" >&2
  echo "         (the filesystem must support security xattrs and not be nosuid)" >&2
  echo "         the app will fall back to sudo -n (root)" >&2
}

check_deps() {
  local missing=""
  python3 - <<'PY' || missing="python packages"
import PIL, dbus  # noqa: F401
PY
  if [ -n "$missing" ]; then
    echo "missing dependencies: install python3-pil python3-dbus" >&2
    exit 1
  fi
  if ! find_tool setcap >/dev/null 2>&1; then
    echo "missing dependencies: install libcap2-bin (no non-root launch without it)" >&2
  fi
}

case "$ACTION" in
  install)
    if [ "${SKIP_DEPS:-0}" != "1" ]; then
      check_deps
    fi
    $SUDO install -d "$APP_ROOT/bin" "$APP_ROOT/applications" \
                       "$APP_ROOT/share/images" "$APP_ROOT/share/mouse-jiggler"
    $SUDO rm -rf "$APP_ROOT/share/mouse-jiggler/mouse_jiggler"
    $SUDO cp -a "$SRC/src/mouse_jiggler" "$APP_ROOT/share/mouse-jiggler/"
    $SUDO find "$APP_ROOT/share/mouse-jiggler" -name '__pycache__' -type d -prune -exec rm -rf {} +
    $SUDO find "$APP_ROOT/share/mouse-jiggler" -type d -exec chmod 755 {} +
    $SUDO find "$APP_ROOT/share/mouse-jiggler" -type f -exec chmod 644 {} +
    $SUDO install -m 755 "$SRC/packaging/mouse-jiggler.sh" "$APP_ROOT/bin/mouse-jiggler"
    $SUDO install -m 644 "$SRC/applaunch/applications/mouse-jiggler.desktop" \
                        "$APP_ROOT/applications/mouse-jiggler.desktop"
    $SUDO install -m 644 "$SRC/applaunch/share/images/mouse-jiggler.png" \
                        "$APP_ROOT/share/images/mouse-jiggler.png"
    if [ "${SKIP_CAPLAUNCH:-0}" != "1" ]; then
      build_caplaunch
    fi
    echo "installed into $APP_ROOT"
    if [ "${SKIP_CAPLAUNCH:-0}" != "1" ]; then
      echo "check the non-root path with: $0 doctor"
    fi
    ;;
  uninstall)
    $SUDO rm -rf /usr/lib/mouse-jiggler "$APP_ROOT/share/mouse-jiggler" \
                "$APP_ROOT/bin/mouse-jiggler" \
                "$APP_ROOT/applications/mouse-jiggler.desktop" \
                "$APP_ROOT/share/images/mouse-jiggler.png"
    echo "removed from $APP_ROOT"
    ;;
  bluetooth-fix)
    $SUDO install -d /etc/systemd/system/bluetooth.service.d
    $SUDO install -m 644 "$SRC/packaging/bluetooth-dropin.conf" \
        /etc/systemd/system/bluetooth.service.d/mouse-jiggler.conf
    $SUDO systemctl daemon-reload
    $SUDO systemctl restart bluetooth
    echo "bluetoothd now runs with -P input (HID device PSMs freed)"
    exit 0
    ;;
  bluetooth-restore)
    $SUDO rm -f /etc/systemd/system/bluetooth.service.d/mouse-jiggler.conf
    $SUDO systemctl daemon-reload
    $SUDO systemctl restart bluetooth
    echo "bluetoothd restored to its default plugin set"
    exit 0
    ;;
  doctor)
    WRAPPER="$APP_ROOT/bin/mouse-jiggler" exec sh "$SRC/tools/doctor.sh"
    ;;
  *)
    echo "usage: $0 [install|uninstall|bluetooth-fix|bluetooth-restore|doctor]" >&2
    exit 2
    ;;
esac

restart_launcher() {
  command -v systemctl >/dev/null 2>&1 || return 0
  if systemctl list-unit-files APPLaunch.service >/dev/null 2>&1 \
     && $SUDO systemctl is-enabled APPLaunch.service >/dev/null 2>&1; then
    $SUDO systemctl restart APPLaunch.service && { echo "APPLaunch restarted"; return 0; }
  fi
  local user="${SUDO_USER:-}"
  if [ -n "$user" ] && [ "$user" != root ]; then
    local uid
    uid=$(id -u "$user")
    if [ -S "/run/user/$uid/bus" ]; then
      local envs="XDG_RUNTIME_DIR=/run/user/$uid DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$uid/bus"
      if [ "$(id -u)" -eq 0 ]; then
        sudo -u "$user" env $envs systemctl --user restart APPLaunch.service \
          && { echo "APPLaunch (user service) restarted"; return 0; }
      else
        env $envs systemctl --user restart APPLaunch.service \
          && { echo "APPLaunch (user service) restarted"; return 0; }
      fi
    fi
  fi
  echo "restart APPLaunch (or reboot) to see the new icon"
}

if [ "$SKIP_RESTART" != "1" ]; then
  restart_launcher
fi

if [ "${SKIP_RESTART:-0}" != "1" ] \
   && ! grep -Rqs -E -- "(-P[[:space:]]+input|--noplugin=input)" \
        /etc/systemd/system/bluetooth.service.d 2>/dev/null; then
  echo
  echo "NOTE: bluetoothd currently owns L2CAP PSMs 0x11/0x13 (HID device role)."
  echo "      Run once:  sudo $0 bluetooth-fix"
  echo "      Undo with: sudo $0 bluetooth-restore"
fi
