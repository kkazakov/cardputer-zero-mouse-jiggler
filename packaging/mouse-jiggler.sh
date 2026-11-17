#!/bin/sh
# APPLaunch entry point.
#
# L2CAP PSMs 0x11/0x13 need CAP_NET_BIND_SERVICE, and APPLaunch runs desktop
# apps as the logged-in user, so re-exec ourselves through sudo. The desktop
# user needs a NOPASSWD rule (the stock CardputerZero image has one).
set -eu

SELF=/usr/share/APPLaunch/bin/mouse-jiggler
APPDIR=/usr/share/APPLaunch/share/mouse-jiggler

if [ "$(id -u)" -ne 0 ]; then
    exec /usr/bin/sudo -n -- "$SELF" "$@"
fi

PYTHONPATH="$APPDIR${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONPATH
exec python3 -m mouse_jiggler "$@"
