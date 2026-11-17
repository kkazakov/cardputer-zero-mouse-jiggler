"""Persisted preferences: selected mode and last bonded host."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .constants import DEFAULT_DEVICE_NAME, MAX_DEVICE_NAME
from .modes import MODES

log = logging.getLogger(__name__)


def default_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "mouse-jiggler" / "config.json"


@dataclass
class Config:
    mode: int = 0
    last_host: str = ""
    device_name: str = DEFAULT_DEVICE_NAME
    path: Path = field(default_factory=default_path, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.mode = int(self.mode) % len(MODES)
        name = " ".join(str(self.device_name or "").split())[:MAX_DEVICE_NAME]
        self.device_name = name or DEFAULT_DEVICE_NAME

    @classmethod
    def load(cls, path: Path | str | None = None) -> Config:
        target = Path(path) if path else default_path()
        data: dict = {}
        try:
            with open(target, encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("config root is not an object")
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            log.warning("ignoring unreadable config %s: %s", target, exc)

        return cls(
            mode=int(data.get("mode", 0) or 0),
            last_host=str(data.get("last_host", "") or ""),
            device_name=str(data.get("device_name", DEFAULT_DEVICE_NAME) or DEFAULT_DEVICE_NAME),
            path=target,
        )

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            payload = {k: v for k, v in asdict(self).items() if k != "path"}
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
                fh.write("\n")
            os.replace(tmp, self.path)
        except OSError as exc:
            log.warning("cannot save config %s: %s", self.path, exc)
