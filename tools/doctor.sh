#!/bin/sh
# Mouse Jiggler — privilege doctor.
#
# Answers one question: on this device, can the app bind the HID L2CAP PSMs
# (0x11/0x13) *without* root?
#
# Run it on the device, as the user APPLaunch runs apps as (usually `pi`), with
# Mouse Jiggler itself stopped. No root needed.
#
#   ./tools/doctor.sh                                # installed layout
#   CAPLAUNCH=./build/caplaunch ./tools/doctor.sh     # a staged build
#
# Exit status: 0 when the non-root path works, 1 otherwise.
set -u

CAPLAUNCH=${CAPLAUNCH:-/usr/lib/mouse-jiggler/caplaunch}
WRAPPER=${WRAPPER:-/usr/share/APPLaunch/bin/mouse-jiggler}
PYTHON=${PYTHON:-python3}

problems=0
notes=0

ok()      { printf '  ok      %s\n' "$*"; }
warn()    { printf '  note    %s\n' "$*"; notes=$((notes + 1)); }
bad()     { printf '  PROBLEM %s\n' "$*"; problems=$((problems + 1)); }
info()    { printf '  %s\n' "$*"; }
section() { printf '\n== %s ==\n' "$*"; }

# Prints "cap_name=flags" for every file capability on a path (empty = none).
# getcap lives in /usr/sbin, which is not on a desktop user's PATH, so the raw
# xattr is decoded here — and *every* bit is reported, named or not, because a
# single unexpected capability on an interpreter is enough to break the app.
file_caps() {
    "$PYTHON" - "$1" <<'PY' 2>/dev/null
import os
import struct
import sys

NAMES = {
    0: "cap_chown", 1: "cap_dac_override", 2: "cap_dac_read_search",
    3: "cap_fowner", 4: "cap_fsetid", 5: "cap_kill", 6: "cap_setgid",
    7: "cap_setuid", 8: "cap_setpcap", 9: "cap_linux_immutable",
    10: "cap_net_bind_service", 11: "cap_net_broadcast", 12: "cap_net_admin",
    13: "cap_net_raw", 14: "cap_ipc_lock", 15: "cap_ipc_owner",
    16: "cap_sys_module", 17: "cap_sys_rawio", 18: "cap_sys_chroot",
    19: "cap_sys_ptrace", 20: "cap_sys_pacct", 21: "cap_sys_admin",
    22: "cap_sys_boot", 23: "cap_sys_nice", 24: "cap_sys_resource",
    25: "cap_sys_time", 26: "cap_sys_tty_config", 27: "cap_mknod",
    28: "cap_lease", 29: "cap_audit_write", 30: "cap_audit_control",
    31: "cap_setfcap", 32: "cap_mac_override", 33: "cap_mac_admin",
    34: "cap_syslog", 35: "cap_wake_alarm", 36: "cap_block_suspend",
    37: "cap_audit_read", 38: "cap_perfmon", 39: "cap_bpf",
    40: "cap_checkpoint_restore",
}
try:
    raw = os.getxattr(sys.argv[1], "security.capability")
except OSError:
    raise SystemExit
magic = struct.unpack_from("<I", raw, 0)[0]
words = struct.unpack_from("<IIII", raw, 4) if len(raw) >= 20 \
    else struct.unpack_from("<II", raw, 4) + (0, 0)
perm = words[0] | (words[2] << 32)
inh = words[1] | (words[3] << 32)
eff = bool(magic & 1)
for bit in range(64):
    mask = 1 << bit
    if (perm | inh) & mask:
        flags = ("p" if perm & mask else "") + ("i" if inh & mask else "")
        print("%s=%s%s" % (NAMES.get(bit, "cap_%d" % bit), flags,
                           "e" if eff else ""))
PY
}

# PIDs of a running Mouse Jiggler (`python3 … -m mouse_jiggler`). Shells whose
# command line merely mentions the module name are ignored.
app_pids() {
    for dir in /proc/[0-9]*; do
        pid=${dir#/proc/}
        [ "$pid" = "$$" ] && continue
        cmd=$(tr '\0' ' ' 2>/dev/null < "$dir/cmdline") || continue
        exe=${cmd%% *}
        case "${exe##*/}" in
            python*) ;;
            *) continue ;;
        esac
        case "$cmd" in
            *"-m mouse_jiggler"*) printf '%s\n' "$pid" ;;
        esac
    done
}

# The probe is meaningless as root: root holds the capability by definition.
# Re-run as the invoking user so the numbers are the ones APPLaunch produces.
if [ "$(id -u)" -eq 0 ]; then
    target=${SUDO_USER:-}
    [ -z "$target" ] || [ "$target" = root ] && target=""
    self=$(cd "$(dirname "$0")" && pwd)/$(basename "$0")
    if [ -n "$target" ] && command -v setpriv >/dev/null 2>&1; then
        printf 're-running as %s (root always holds the capability)\n' "$target"
        exec setpriv --reuid="$(id -u "$target")" --regid="$(id -g "$target")" \
             --init-groups sh "$self" "$@"
    fi
    printf 'refusing to probe as root: root holds the capability by definition.\n' >&2
    printf 'run this as the desktop user (on the stock image: pi).\n' >&2
    exit 2
fi

# --------------------------------------------------------------------------
section "target"
info "$(hostname) / $(uname -m) / kernel $(uname -r)"
info "$(id -un) (uid $(id -u))"
if [ ! -e /usr/share/APPLaunch ] && [ ! -x "$WRAPPER" ]; then
    warn "no APPLaunch install here: this does not look like the CardputerZero."
    warn "the doctor inspects the machine the app runs on — run it on the device."
fi

# --------------------------------------------------------------------------
section "capability launcher: $CAPLAUNCH"
if [ ! -e "$CAPLAUNCH" ]; then
    bad "missing: install.sh did not build it (needs a C compiler); the wrapper falls back to sudo -n"
else
    if [ -x "$CAPLAUNCH" ]; then
        ok "executable — $(ls -ld "$CAPLAUNCH" | awk '{print $1, $3 ":" $4}')"
    else
        bad "not executable: chmod 755 $CAPLAUNCH"
    fi

    caps=$(file_caps "$CAPLAUNCH" | tr '\n' ' ')
    case "$caps" in
        *cap_net_bind_service*) ok "file capability: $caps" ;;
        "")  bad "no file capability: sudo setcap cap_net_bind_service=pie $CAPLAUNCH" ;;
        *)   bad "unexpected file capability: $caps" ;;
    esac

    if command -v findmnt >/dev/null 2>&1; then
        mnt=$(findmnt -no TARGET,FSTYPE,OPTIONS --target "$CAPLAUNCH" 2>/dev/null || true)
        info "mount ${mnt:-unknown}"
        case "$mnt" in
            *nosuid*) bad "mounted nosuid: file capabilities are ignored at exec" ;;
            *noexec*) bad "mounted noexec: the launcher cannot run from here" ;;
        esac
    fi
fi

# --------------------------------------------------------------------------
# The decisive test: run the launcher exactly as the wrapper does, with a
# sitecustomize that reports the capabilities Python actually received and then
# tries to bind HID PSM 19. None of the app runs.
section "probe: what python3 receives through the launcher"
if [ ! -x "$CAPLAUNCH" ]; then
    bad "skipped: no launcher to probe"
else
    probe=$(mktemp -d 2>/dev/null || true)
    if [ -z "$probe" ]; then
        bad "skipped: cannot create a temporary directory"
    else
        cat > "$probe/sitecustomize.py" <<'PY'
import os
import socket
import sys

for line in open("/proc/self/status", encoding="utf-8"):
    if line.startswith(("Uid:", "CapEff:", "CapAmb:", "NoNewPrivs:")):
        sys.stderr.write("MJPROBE caps %s\n" % line.strip())
try:
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET,
                         socket.BTPROTO_L2CAP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("00:00:00:00:00:00", 19))
    sock.close()
    sys.stderr.write("MJPROBE bind: ok\n")
except Exception as exc:                       # report whatever went wrong
    sys.stderr.write("MJPROBE bind: %s: %s\n" % (type(exc).__name__, exc))
sys.stderr.flush()
os._exit(0)
PY
        out=$(PYTHONPATH="$probe" "$CAPLAUNCH" 2>&1 || true)
        rm -rf "$probe"

        printf '%s\n' "$out" | grep '^MJPROBE caps' | sed 's/^MJPROBE caps /  caps    /'
        bind=$(printf '%s\n' "$out" | grep '^MJPROBE bind:' | sed 's/^MJPROBE bind: //')

        if printf '%s\n' "$out" | grep -q '^MJPROBE bind: ok'; then
            ok "bound PSM 19 — the capability reaches python3"
        else
            case "$bind" in
                *PermissionError*|*"Operation not permitted"*)
                    bad "$bind — CAP_NET_BIND_SERVICE does not reach python3" ;;
                *"Address already in use"*)
                    if [ -n "$(app_pids)" ]; then
                        warn "$bind — held by a running Mouse Jiggler; stop it and retry"
                    else
                        bad "$bind — bluetoothd's input plugin owns it: sudo ./install.sh bluetooth-fix"
                    fi ;;
                "")
                    bad "no output from the probe; run the launcher by hand to see why" ;;
                *)
                    bad "$bind" ;;
            esac
        fi
    fi
fi

# --------------------------------------------------------------------------
# A file capability on the interpreter itself is fatal and easy to create by
# accident: execve() zeroes the ambient set when the file it runs is privileged,
# so caplaunch's CAP_NET_BIND_SERVICE is dropped and Python inherits whatever
# the interpreter carries instead.
section "interpreter: $PYTHON"
py=$(command -v "$PYTHON" 2>/dev/null || echo "$PYTHON")
real=$(readlink -f "$py" 2>/dev/null || echo "$py")
info "$py -> $real"
pycaps=$(file_caps "$real" | tr '\n' ' ')
case "$pycaps" in
    "") ok "no file capabilities (the ambient handoff survives exec)" ;;
    *)  bad "the interpreter carries file capabilities: $pycaps"
        info "  exec'ing a privileged file zeroes the ambient set, so"
        info "  CAP_NET_BIND_SERVICE never reaches Python (and every Python"
        info "  program gets that capability): sudo setcap -r $real" ;;
esac

# --------------------------------------------------------------------------
section "wrapper: $WRAPPER"
if [ ! -x "$WRAPPER" ]; then
    bad "missing or not executable (not installed yet?)"
elif ! grep -q 'caplaunch' "$WRAPPER" 2>/dev/null; then
    bad "predates the capability launcher: reinstall"
else
    ok "routes through the capability launcher"
fi

# --------------------------------------------------------------------------
section "bluetoothd"
bt=$(pgrep -a bluetoothd 2>/dev/null || true)
if [ -z "$bt" ]; then
    bad "not running"
else
    info "$bt"
    case "$bt" in
        *"-P input"*|*"--noplugin=input"*) ok "input plugin disabled — PSMs 0x11/0x13 are free" ;;
        *) warn "input plugin active — it holds the HID PSMs (sudo ./install.sh bluetooth-fix)" ;;
    esac
fi

# --------------------------------------------------------------------------
section "runtime"
if [ -n "$(app_pids)" ]; then
    for pid in $(app_pids); do
        info "pid $pid as user $(ps -o user= -p "$pid" 2>/dev/null)"
        grep -E '^(Uid|CapEff|NoNewPrivs):' "/proc/$pid/status" 2>/dev/null \
            | sed 's/^/          /'
    done
else
    warn "app not running — stop it before trusting the probe above"
fi
for dep in dbus gi PIL; do
    if "$PYTHON" -c "import $dep" >/dev/null 2>&1; then
        ok "python3 $dep"
    else
        bad "python3 $dep is missing"
    fi
done

# --------------------------------------------------------------------------
printf '\n== verdict ==\n'
if [ "$problems" -eq 0 ]; then
    printf '  PASS  non-root launch can bind the HID PSMs'
    [ "$notes" -gt 0 ] && printf '  (%s note(s) above)' "$notes"
    printf '\n'
    exit 0
fi
printf '  FAIL  %s problem(s) above\n' "$problems"
exit 1
