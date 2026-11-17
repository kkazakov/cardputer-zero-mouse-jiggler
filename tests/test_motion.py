import random

from mouse_jiggler.hid.motion import MotionEngine
from mouse_jiggler.modes import MODES


def test_slow_alternates_two_pixels():
    engine = MotionEngine(0)
    assert [engine.next_vector() for _ in range(4)] == [(2, 0), (-2, 0), (2, 0), (-2, 0)]


def test_fast_alternates_five_pixels():
    engine = MotionEngine(1)
    assert [engine.next_vector() for _ in range(4)] == [(5, 0), (-5, 0), (5, 0), (-5, 0)]


def test_jiggle_pairs_are_inverse():
    engine = MotionEngine(2, rng=random.Random(7))
    for _ in range(20):
        vector = engine.next_vector()
        inverse = engine.next_vector()
        assert inverse == (-vector[0], -vector[1])


def test_jiggle_magnitude_is_between_20_and_30():
    engine = MotionEngine(2, rng=random.Random(11))
    for _ in range(50):
        dx, dy = engine.next_vector()
        assert 20 <= (dx * dx + dy * dy) ** 0.5 <= 30
        engine.next_vector()


def test_jiggle_drift_is_bounded():
    engine = MotionEngine(2, rng=random.Random(3))
    x = y = 0
    for _ in range(200):
        dx, dy = engine.next_vector()
        x += dx
        y += dy
    assert (x, y) == (0, 0)


def test_mode_periods_match_the_spec():
    assert [mode.period for mode in MODES] == [30.0, 10.0, 0.1]
    assert MODES[0].subtitle == "Slow · 2 px / 30 s"
    assert MODES[2].subtitle == "Jiggle · 20-30 px / 100 ms"
