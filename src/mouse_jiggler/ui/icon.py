"""Launcher icon: pointer, motion trails and a Bluetooth badge on a tile.

The artwork is the app's own: a dark rounded plate with the pointer, two motion
trails and a Bluetooth badge. The plate has **no border** — APPLaunch already
draws its own grey rounded frame around every icon, so an outline baked into the
PNG shows up as a doubled frame.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from . import icons, theme

SIZE = 256          # master artwork size; APPLaunch copy is downscaled


def render() -> Image.Image:
    s = SIZE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # No outline: the launcher draws its own frame around the icon.
    d.rounded_rectangle([4, 4, s - 5, s - 5], 54, fill=theme.BACKGROUND + (255,))

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


def render_at(size: int) -> Image.Image:
    if size == SIZE:
        return render()
    return render().resize((size, size), Image.LANCZOS)


__all__ = ["render", "render_at", "SIZE"]
