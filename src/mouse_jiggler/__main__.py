"""Command line entry point: ``python3 -m mouse_jiggler``."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys

from . import __version__
from .app import App
from .bt.transport import BluetoothTransport
from .config import Config
from .input.keypad import Keypad, KeypadError
from .platform.fb import Framebuffer, FramebufferError

log = logging.getLogger("mouse_jiggler")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mouse-jiggler",
        description="Bluetooth mouse jiggler for the M5Stack CardputerZero",
    )
    parser.add_argument("--fb", metavar="PATH", help="framebuffer device (default: auto)")
    parser.add_argument("--keys", metavar="PATH", help="input event device (default: auto)")
    parser.add_argument("--adapter", default="hci0", help="Bluetooth adapter (default: hci0)")
    parser.add_argument("--config", metavar="PATH", help="config file path")
    parser.add_argument("--pairing-seconds", type=float, default=180.0,
                        help="pairing window length (default: 180)")
    parser.add_argument("--debug", action="store_true", help="verbose logging")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def has_net_bind_service() -> bool:
    """True when the process holds CAP_NET_BIND_SERVICE (root or file caps)."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return True
    try:
        with open("/proc/self/status", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("CapEff:"):
                    return bool(int(line.split()[1], 16) & (1 << 10))
    except OSError:
        pass
    return False


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    if not has_net_bind_service():
        log.warning(
            "no CAP_NET_BIND_SERVICE: L2CAP PSMs 0x11/0x13 cannot be bound. "
            "Start the app through /usr/share/APPLaunch/bin/mouse-jiggler "
            "(capability launcher) or check 'sudo ./install.sh doctor'."
        )

    config = Config.load(args.config)

    try:
        display = Framebuffer(args.fb).open()
    except FramebufferError as exc:
        log.error("%s", exc)
        return 1

    keypad = None
    try:
        keypad = Keypad.open(args.keys)
    except KeypadError as exc:
        log.warning("%s", exc)

    transport = BluetoothTransport(args.adapter, device_name=config.device_name)
    app = App(
        transport,
        display,
        keypad,
        config,
        pairing_seconds=args.pairing_seconds,
    )

    def _stop(_signum, _frame):
        log.info("signal received, exiting")
        app.stop()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    status = 0
    try:
        app.run()
    finally:
        if keypad is not None:
            keypad.close()
        display.close()
        logging.shutdown()
        sys.stdout.flush()
        sys.stderr.flush()
        # Skip interpreter teardown: the GLib/dbus-python threads that served the
        # pairing agent can fault inside libdbus while Python finalises objects
        # (observed as SIGSEGV when bluetoothd failed mid-setup).
        os._exit(status)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
