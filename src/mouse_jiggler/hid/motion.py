"""Movement vectors and scheduling helpers for the three modes.

The engine is pure: it does not sleep, send or touch the clock. The app decides
when a tick is due and asks for the next vector.

Slow / Fast alternate direction every tick, so the pointer oscillates around a
fixed point instead of walking across the screen. Jiggle draws a random vector
and undoes it on the following tick for the same reason:

    tick 0: +v      tick 1: -v      tick 2: +w      tick 3: -w ...

Net displacement is therefore 0 px for Slow/Fast and <= 30 px for Jiggle.
"""

from __future__ import annotations

import math
import random

from ..modes import DEFAULT_MODE, MODES
from .reports import clamp


class MotionEngine:
    def __init__(self, mode: int = DEFAULT_MODE, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()
        self._mode = 0
        self._tick = 0
        self._last = (0, 0)
        self.set_mode(mode)

    @property
    def mode(self) -> int:
        return self._mode

    @property
    def mode_info(self):
        return MODES[self._mode]

    @property
    def period(self) -> float:
        return MODES[self._mode].period

    def set_mode(self, index: int) -> None:
        self._mode = index % len(MODES)
        self.reset()

    def reset(self) -> None:
        self._tick = 0
        self._last = (0, 0)

    def next_vector(self) -> tuple[int, int]:
        mode = MODES[self._mode]
        if mode.key == "jiggle":
            vector = self._jiggle_vector()
        else:
            step = mode.step
            vector = (step if self._tick % 2 == 0 else -step, 0)
        self._last = vector
        self._tick += 1
        return vector

    def _jiggle_vector(self) -> tuple[int, int]:
        mode = MODES[self._mode]
        if self._tick % 2 == 1 and self._last != (0, 0):
            return (-self._last[0], -self._last[1])
        angle = self._rng.uniform(0.0, 2.0 * math.pi)
        magnitude = self._rng.uniform(float(mode.jiggle_min), float(mode.jiggle_max))
        vector = (
            clamp(round(magnitude * math.cos(angle))),
            clamp(round(magnitude * math.sin(angle))),
        )
        return vector if vector != (0, 0) else (mode.jiggle_min, 0)


def ticks_per_minute(mode: int) -> float:
    return 60.0 / MODES[mode].period
