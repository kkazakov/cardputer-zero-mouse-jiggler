"""Design tokens and geometry for the Mouse Jiggler UI.

Values mirror geo-tp/Ultimate-Remote's Linux framebuffer renderer (MIT) so the
app sits naturally next to it on the same 320x170 panel. See docs/ui-spec.md.
"""

from __future__ import annotations

from ..modes import MODES, Mode  # noqa: F401  (re-exported for the UI)

W, H = 320, 170
FOOTER_H = 19

# ---- palette -------------------------------------------------------------
BACKGROUND = (0x0B, 0x11, 0x1A)
PANEL = (0x14, 0x1F, 0x2D)
CARD = (0x1B, 0x2B, 0x37)
BORDER = (0x27, 0x37, 0x4A)
PRIMARY = (0x88, 0xF0, 0xB3)
TEXT = (0xED, 0xF3, 0xFA)
MUTED = (0x95, 0xA6, 0xBB)
BLUE = (0x80, 0xBA, 0xFF)
AMBER = (0xFF, 0xD1, 0x8B)
VIOLET = (0xBD, 0xA7, 0xFF)
INK = (0x10, 0x24, 0x1C)
PINK = (0xF2, 0x9E, 0xC0)

# ---- type scale ----------------------------------------------------------
SMALL, BODY, TITLE = 10, 12, 16

# ---- geometry ------------------------------------------------------------
HEADER_LINE_Y = 25
HEADER_ICON = (8, 4, 18)
HEADER_TITLE = (33, 7)
BADGE_Y, BADGE_H, BADGE_RADIUS = 4, 17, 5

CENTER_CARD = (87, 34, 146, 99)
SIDE_CARD_W, SIDE_CARD_H, SIDE_CARD_Y = 71, 77, 46
LEFT_CARD_X, RIGHT_CARD_X = 7, 242
CARD_RADIUS = 11

DOTS_Y = 141
DOT_ACTIVE_W, DOT_IDLE_W, DOT_H = 14, 5, 4
DOTS_SPACING = 12
DOT_ADVANCE_ACTIVE = 21

CAROUSEL = ("pair", "start", "mode", "rename")


def accent_for(item: str, running: bool = False) -> tuple[int, int, int]:
    if item == "pair":
        return BLUE
    if item == "mode":
        return VIOLET
    if item == "rename":
        return PINK
    return AMBER if running else PRIMARY
