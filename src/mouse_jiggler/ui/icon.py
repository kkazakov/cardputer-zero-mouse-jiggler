"""Launcher icon: pointer + motion ticks + Bluetooth badge.

256x256 RGBA, safe at 48 px. Uses only palette colours so it matches the app.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from . import icons, theme

SIZE = 256


def render() -> Image.Image:
    s = SIZE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    d.rounded_rectangle([4, 4, s - 5, s - 5], 54, fill=theme.BACKGROUND + (255,),
                        outline=theme.PRIMARY + (255,), width=6)

    trails = ((92, 40, theme.AMBER), (122, 54, theme.AMBER), (152, 32, theme.BORDER))
    for y, length, color in trails:
        d.rounded_rectangle([38, y, 38 + length, y + 8], 4, fill=color + (255,))

    points = [(88, 40), (88, 190), (122, 154), (147, 205), (167, 195), (142, 145), (185, 145)]
    d.line(points + [points[0]], fill=theme.BACKGROUND + (255,), width=14, joint="curve")
    d.polygon(points, fill=theme.PRIMARY + (255,))

    cx, cy, radius = 206, 56, 27
    d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=theme.AMBER + (255,))
    rune = icons.bluetooth(30, theme.BACKGROUND)
    img.paste(rune, (cx - 15, cy - 15), rune)
    return img


__all__ = ["render", "SIZE"]
