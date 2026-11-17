"""DejaVu Sans loading and small text helpers for the framebuffer UI.

The reference UI bakes DejaVu Sans at 10 / 12 / 16 px into bitmaps. We load the
same faces with Pillow, which gives identical metrics without generating a
glyph header.
"""

from __future__ import annotations

import os
from functools import lru_cache

from PIL import ImageDraw, ImageFont

_CANDIDATES = ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation")

try:  # matplotlib bundles DejaVu, useful for desktop previews
    import matplotlib

    _CANDIDATES = (
        _CANDIDATES[0],
        os.path.join(matplotlib.get_data_path(), "fonts", "ttf"),
        _CANDIDATES[1],
    )
except Exception:  # pragma: no cover - preview convenience only
    pass


@lru_cache(maxsize=16)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf") if bold else ("DejaVuSans.ttf",)
    for directory in _CANDIDATES:
        for name in names:
            path = os.path.join(directory, name)
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except OSError:
                    continue
    return ImageFont.load_default(size)


def width(text: str, size: int, bold: bool = False) -> int:
    return int(round(font(size, bold).getlength(text)))


def draw(d: ImageDraw.ImageDraw, x: int, y: int, text: str, size: int,
         color: tuple[int, int, int], bold: bool = False,
         center_at: int | None = None) -> None:
    if center_at is not None:
        x = center_at - width(text, size, bold) // 2
    d.text((x, y), text, font=font(size, bold), fill=color)


def ellipsize(text: str, size: int, max_width: int, bold: bool = False) -> str:
    """Trim with an ASCII ellipsis, like the reference's fitText()."""
    if width(text, size, bold) <= max_width:
        return text
    if width("...", size, bold) > max_width:
        return ""
    while text and width(text + "...", size, bold) > max_width:
        text = text[:-1]
    return text + "..."
