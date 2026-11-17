#!/bin/sh
# APPLaunch entry point.
#
# L2CAP PSMs 0x11/0x13 (HID) are privileged. Preferred path: the launcher in
# /usr/lib/mouse-jiggler/caplaunch carries CAP_NET_BIND_SERVICE as a file
# capability, so the app runs as the desktop user with exactly one capability.
# Fallbacks, in order: run directly (already root), or re-exec through sudo.
set -eu

CAPLAUNCH=/usr/lib/mouse-jiggler/caplaunch
APPDIR=/usr/share/APPLaunch/share/mouse-jiggler
SELF=/usr/share/APPLaunch/bin/mouse-jiggler

PYTHONPATH="$APPDIR${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONPATH

if [ "$(id -u)" -ne 0 ]; then
    if [ -x "$CAPLAUNCH" ]; then
        rc=0
        "$CAPLAUNCH" "$@" || rc=$?
        # 77: the launcher could not obtain CAP_NET_BIND_SERVICE (no file
        # capability, nosuid filesystem, ...). Root still works, so fall back
        # to sudo -n instead of showing a dead end. Any other status is the
        # app's own.
        if [ "$rc" -ne 77 ]; then
            exit "$rc"
        fi
        echo "mouse-jiggler: capability launcher unavailable, falling back to sudo" >&2
    fi
    exec /usr/bin/sudo -n -- "$SELF" "$@"
fi

exec python3 -m mouse_jiggler "$@"
