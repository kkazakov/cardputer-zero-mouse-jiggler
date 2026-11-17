#!/usr/bin/env bash
# Install (or remove) Mouse Jiggler in APPLaunch.
# Run on the CardputerZero; needs root for /usr/share and L2CAP at runtime.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="${APP_ROOT:-/usr/share/APPLaunch}"
SKIP_RESTART="${SKIP_RESTART:-0}"
SUDO=""
if [ "$(id -u)" -ne 0 ] && [ ! -w "$(dirname "$APP_ROOT")" ] && [ ! -w "$APP_ROOT" ]; then
  SUDO="sudo"
fi

ACTION="${1:-install}"

check_deps() {
  local missing=""
  python3 - <<'PY' || missing="python packages"
import PIL, dbus  # noqa: F401
PY
  if [ -n "$missing" ]; then
    echo "missing dependencies: install python3-pil python3-dbus" >&2
    exit 1
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
    echo "installed into $APP_ROOT"
    ;;
  uninstall)
    $SUDO rm -rf "$APP_ROOT/share/mouse-jiggler" \
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
  *)
    echo "usage: $0 [install|uninstall|bluetooth-fix|bluetooth-restore]" >&2
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
