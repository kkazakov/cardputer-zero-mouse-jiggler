"""Application states, one per screen family."""

from __future__ import annotations

from enum import Enum


class State(Enum):
    OFFLINE = "offline"      # no host connection
    PAIRING = "pairing"      # discoverable window
    CONNECTED = "connected"  # host linked, not moving
    RUNNING = "running"      # host linked, reports being sent
    CONFIRM = "confirm"      # "re-pair?" confirmation page
    RENAME = "rename"        # on-screen name editor
    ERROR = "error"          # Bluetooth setup failed
