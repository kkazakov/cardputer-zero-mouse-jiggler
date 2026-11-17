"""The three movement modes — shared by the motion engine and the UI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Mode:
    key: str
    label: str
    period: float          # seconds between reports
    subtitle: str          # exact string shown in the UI
    step: int = 0          # px per tick for the fixed modes
    jiggle_min: int = 0
    jiggle_max: int = 0


MODES: tuple[Mode, ...] = (
    Mode("slow", "Slow", 30.0, "Slow · 2 px / 30 s", step=2),
    Mode("fast", "Fast", 10.0, "Fast · 5 px / 10 s", step=5),
    Mode("jiggle", "Jiggle", 0.1, "Jiggle · 20-30 px / 100 ms", jiggle_min=20, jiggle_max=30),
)

DEFAULT_MODE = 0
