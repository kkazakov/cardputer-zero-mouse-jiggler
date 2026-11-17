"""Vector icons rasterised at 4x and downsampled, like the reference UI.

Each function returns an RGBA image sized `size` x `size`. The drawing grid is
32 x 32 units, so the same shape works at 18, 25, 28 and 34 px.
"""

from __future__ import annotations

from collections.abc import Callable

from PIL import Image, ImageDraw

Color = tuple[int, int, int]
SUPERSAMPLE = 4


def _canvas(size: int) -> tuple[Image.Image, ImageDraw.ImageDraw, float]:
    layer = Image.new("RGBA", (size * SUPERSAMPLE, size * SUPERSAMPLE), (0, 0, 0, 0))
    return layer, ImageDraw.Draw(layer), SUPERSAMPLE * size / 32.0


def _finish(layer: Image.Image, size: int) -> Image.Image:
    return layer.resize((size, size), Image.LANCZOS)


def play(size: int, color: Color) -> Image.Image:
    layer, d, u = _canvas(size)
    d.polygon([(10 * u, 6 * u), (27 * u, 16 * u), (10 * u, 26 * u)], fill=color + (255,))
    return _finish(layer, size)


def stop(size: int, color: Color) -> Image.Image:
    layer, d, u = _canvas(size)
    d.rounded_rectangle([9 * u, 9 * u, 23 * u, 23 * u], radius=3 * u, fill=color + (255,))
    return _finish(layer, size)


def bluetooth(size: int, color: Color) -> Image.Image:
    layer, d, u = _canvas(size)
    stroke = max(1, int(2.6 * u))
    d.line([(16 * u, 4 * u), (16 * u, 28 * u)], fill=color + (255,), width=stroke)
    d.line([(16 * u, 4 * u), (24 * u, 10 * u), (16 * u, 16 * u)],
           fill=color + (255,), width=stroke, joint="curve")
    d.line([(16 * u, 16 * u), (24 * u, 22 * u), (16 * u, 28 * u)],
           fill=color + (255,), width=stroke, joint="curve")
    return _finish(layer, size)


def cycle(size: int, color: Color) -> Image.Image:
    layer, d, u = _canvas(size)
    stroke = max(1, int(2.4 * u))
    d.arc([7 * u, 7 * u, 25 * u, 25 * u], start=35, end=300, fill=color + (255,), width=stroke)
    d.polygon([(25.6 * u, 8.2 * u), (20.6 * u, 8.6 * u), (24.6 * u, 13.0 * u)], fill=color + (255,))
    return _finish(layer, size)


def cursor(size: int, color: Color) -> Image.Image:
    layer, d, u = _canvas(size)
    points = [(10, 4), (10, 26), (14.5, 20.5), (17.5, 28), (21, 26.5), (18, 19), (25, 19)]
    d.polygon([(x * u, y * u) for x, y in points], fill=color + (255,))
    return _finish(layer, size)


def pencil(size: int, color: Color) -> Image.Image:
    layer, d, u = _canvas(size)
    body = max(1, int(6.5 * u))
    d.line([(13 * u, 22 * u), (25 * u, 10 * u)], fill=color + (255,), width=body)
    d.polygon([(6 * u, 30 * u), (12 * u, 27 * u), (9 * u, 22 * u)], fill=color + (255,))
    d.line([(11 * u, 21 * u), (25 * u, 7 * u)], fill=color + (255,), width=max(1, int(2 * u)))
    return _finish(layer, size)


def alert(size: int, color: Color) -> Image.Image:
    layer, d, u = _canvas(size)
    stroke = max(1, int(2.4 * u))
    d.rounded_rectangle([6 * u, 5 * u, 26 * u, 27 * u], radius=4 * u,
                        outline=color + (255,), width=stroke)
    d.line([(16 * u, 11 * u), (16 * u, 19 * u)], fill=color + (255,), width=stroke)
    d.ellipse([15 * u, 21.5 * u, 17 * u, 23.5 * u], fill=color + (255,))
    return _finish(layer, size)


ICONS: dict[str, Callable[[int, Color], Image.Image]] = {
    "play": play,
    "stop": stop,
    "bluetooth": bluetooth,
    "cycle": cycle,
    "cursor": cursor,
    "pencil": pencil,
    "alert": alert,
}
