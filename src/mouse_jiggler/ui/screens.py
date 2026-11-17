"""Compose the 320x170 screens.

Each render_* function returns a new RGB image. The layout follows
docs/ui-spec.md and is kept deliberately close to Ultimate-Remote's Linux
renderer so the two apps look like siblings on the device.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw

from ..constants import DEFAULT_DEVICE_NAME, MAX_DEVICE_NAME
from . import fonts, icons, theme


@dataclass(frozen=True)
class HomeState:
    """Everything the home screen needs to know."""

    selected: int = 1          # index into theme.CAROUSEL
    running: bool = False
    mode: int = 0              # index into theme.MODES
    elapsed: str = "00:00:00"
    reports: int = 0
    paired: bool = True
    device_name: str = DEFAULT_DEVICE_NAME

    def selected_item(self) -> str:
        return theme.CAROUSEL[self.selected % len(theme.CAROUSEL)]


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (theme.W, theme.H), theme.BACKGROUND)
    return img, ImageDraw.Draw(img)


def _paste(img: Image.Image, icon: Image.Image, x: int, y: int) -> None:
    img.paste(icon, (x, y), icon)


def _text(d, x, y, s, size, color, bold=False, center_at=None):
    fonts.draw(d, x, y, s, size, color, bold=bold, center_at=center_at)


# --------------------------------------------------------------------------
# chrome
# --------------------------------------------------------------------------

def _header(img, d, badge: str, color) -> None:
    badge_w = fonts.width(badge, theme.SMALL) + 14
    badge_x = theme.W - badge_w - 8
    _paste(img, icons.bluetooth(16, color), badge_x - 24, 5)
    _paste(img, icons.cursor(*theme.HEADER_ICON[2:], theme.PRIMARY), *theme.HEADER_ICON[:2])
    _text(d, *theme.HEADER_TITLE, "MOUSE JIGGLER", theme.SMALL, theme.TEXT)
    d.rounded_rectangle([badge_x, theme.BADGE_Y, badge_x + badge_w, theme.BADGE_Y + theme.BADGE_H],
                        theme.BADGE_RADIUS, fill=theme.PANEL)
    _text(d, badge_x + 7, 7, badge, theme.SMALL, color)


def _footer(d, hints: list[tuple[str, str]]) -> None:
    y = theme.H - theme.FOOTER_H
    d.line([(8, y), (theme.W - 8, y)], fill=theme.BORDER)
    slot = (theme.W - 16) // max(1, len(hints))
    x = 8
    for key, label in hints:
        key_w = fonts.width(key, theme.SMALL) + 8
        d.rounded_rectangle([x, y + 4, x + key_w, y + 16], 3, fill=theme.BORDER)
        _text(d, x + 4, y + 4, key, theme.SMALL, theme.TEXT)
        _text(d, x + key_w + 5, y + 4, label, theme.SMALL, theme.MUTED)
        x += slot


def _card(d, x, y, w, h, accent, active: bool) -> None:
    d.rounded_rectangle([x, y, x + w - 1, y + h - 1], theme.CARD_RADIUS, fill=accent)
    d.rounded_rectangle([x + 1, y + 1, x + w - 2, y + h - 2], theme.CARD_RADIUS - 1,
                        fill=theme.CARD if active else theme.PANEL)
    if active:
        d.rounded_rectangle([x + w // 2 - 16, y, x + w // 2 + 16, y + 3], 1, fill=accent)


def _dots(d, selected: int, accent) -> None:
    count = len(theme.CAROUSEL)
    total = (count - 1) * theme.DOTS_SPACING + theme.DOT_ACTIVE_W
    x = (theme.W - total) // 2
    for i in range(count):
        active = i == selected
        d.rounded_rectangle([x, theme.DOTS_Y,
                             x + (theme.DOT_ACTIVE_W if active else theme.DOT_IDLE_W) - 1,
                             theme.DOTS_Y + theme.DOT_H - 1],
                            2, fill=accent if active else theme.BORDER)
        x += theme.DOT_ADVANCE_ACTIVE if active else theme.DOTS_SPACING


# --------------------------------------------------------------------------
# home
# --------------------------------------------------------------------------

def _items(state: HomeState) -> dict[str, dict]:
    running = state.running
    return {
        "pair": {
            "title": "Pair",
            "subtitle": "Connected host" if state.paired else "Connect a host",
            "accent": theme.BLUE,
            "icon": icons.bluetooth,
        },
        "start": {
            "title": "Stop" if running else "Start",
            "subtitle": (f"{state.elapsed} · {state.reports} reports" if running
                         else theme.MODES[state.mode].subtitle),
            "accent": theme.AMBER if running else theme.PRIMARY,
            "icon": icons.stop if running else icons.play,
        },
        "mode": {
            "title": "Mode",
            "subtitle": theme.MODES[state.mode].subtitle,
            "accent": theme.VIOLET,
            "icon": icons.cycle,
        },
        "rename": {
            "title": "Rename",
            "subtitle": fonts.ellipsize(state.device_name, theme.SMALL, 134),
            "accent": theme.PINK,
            "icon": icons.pencil,
        },
    }


def render_home(state: HomeState) -> Image.Image:
    img, d = _canvas()
    if state.running:
        badge, color = "RUNNING", theme.AMBER
    elif state.paired:
        badge, color = "CONNECTED", theme.PRIMARY
    else:
        badge, color = "OFFLINE", theme.MUTED
    _header(img, d, badge, color)

    items = _items(state)
    selected = state.selected % len(theme.CAROUSEL)
    center = items[theme.CAROUSEL[selected]]
    left = items[theme.CAROUSEL[(selected - 1) % len(theme.CAROUSEL)]]
    right = items[theme.CAROUSEL[(selected + 1) % len(theme.CAROUSEL)]]

    for item, x in ((left, theme.LEFT_CARD_X), (right, theme.RIGHT_CARD_X)):
        w, h = theme.SIDE_CARD_W, theme.SIDE_CARD_H
        _card(d, x, theme.SIDE_CARD_Y, w, h, theme.BORDER, False)
        _paste(img, item["icon"](25, theme.MUTED),
               x + (w - 25) // 2, theme.SIDE_CARD_Y + 13)
        _text(d, 0, theme.SIDE_CARD_Y + 52, item["title"], theme.SMALL, theme.MUTED,
              center_at=x + w // 2)

    x, y, w, h = theme.CENTER_CARD
    _card(d, x, y, w, h, center["accent"], True)
    _paste(img, center["icon"](34, center["accent"]), x + (w - 34) // 2, y + 11)
    _text(d, 0, y + 52, center["title"], theme.TITLE, theme.TEXT, bold=True,
          center_at=x + w // 2)
    _text(d, 0, y + 79, center["subtitle"], theme.SMALL, theme.MUTED, center_at=x + w // 2)

    _dots(d, selected, center["accent"])
    _footer(d, [("Z / C", "Select"), ("OK", "Action"), ("ESC", "Exit")])
    return img


# --------------------------------------------------------------------------
# status pages
# --------------------------------------------------------------------------

def _status_page(badge: str, badge_color, icon: Image.Image, title: str,
                 lines: list[str], hints: list[tuple[str, str]]) -> Image.Image:
    img, d = _canvas()
    _header(img, d, badge, badge_color)
    _paste(img, icon, theme.W // 2 - 14, 35)
    _text(d, 0, 73, title, theme.TITLE, theme.TEXT, bold=True, center_at=theme.W // 2)
    y = 103
    for line in lines:
        size = theme.BODY if y == 103 else theme.SMALL
        _text(d, 0, y, line, size, theme.MUTED, center_at=theme.W // 2)
        y += 20
        if y > theme.H - theme.FOOTER_H - 14:
            break
    _footer(d, hints)
    return img


def render_pairing(
    seconds_left: int = 161, device_name: str = "CardputerZero Mouse"
) -> Image.Image:
    minutes, seconds = divmod(max(0, seconds_left), 60)
    return _status_page(
        badge=f"PAIRING {minutes}:{seconds:02d}",
        badge_color=theme.BLUE,
        icon=icons.bluetooth(28, theme.BLUE),
        title="Pairing",
        lines=[device_name, "Add it in your computer's Bluetooth settings"],
        hints=[("ESC", "Cancel")],
    )


def render_confirm(host: str) -> Image.Image:
    return _status_page(
        badge="CONNECTED",
        badge_color=theme.PRIMARY,
        icon=icons.bluetooth(28, theme.BLUE),
        title="Re-pair?",
        lines=[f"This forgets {host}", "Pair again from scratch"],
        hints=[("OK", "Forget"), ("ESC", "Cancel")],
    )


def render_rename(text: str, *, limit: int = MAX_DEVICE_NAME, cursor: bool = True,
                  connected: bool = True) -> Image.Image:
    """Text-entry page for the Bluetooth device name."""
    img, d = _canvas()
    if connected:
        _header(img, d, "CONNECTED", theme.PRIMARY)
    else:
        _header(img, d, "OFFLINE", theme.MUTED)

    _text(d, 0, 31, "Mouse name", theme.TITLE, theme.TEXT, bold=True, center_at=theme.W // 2)

    d.rounded_rectangle([20, 56, 299, 95], 8, fill=theme.PINK)
    d.rounded_rectangle([21, 57, 298, 94], 7, fill=theme.PANEL)
    shown = text or "Type a name"
    _text(d, 30, 66, shown, theme.TITLE, theme.TEXT if text else theme.MUTED, bold=bool(text))
    if cursor:
        cursor_x = 30 + (fonts.width(shown, theme.TITLE, True) + 2 if text else 0)
        d.rectangle([cursor_x, 64, cursor_x + 1, 86], fill=theme.PINK)

    counter = f"{len(text)}/{limit}"
    _text(d, 299 - fonts.width(counter, theme.SMALL), 101, counter, theme.SMALL, theme.MUTED)
    _text(d, 0, 115, "Shown to other Bluetooth devices", theme.SMALL, theme.MUTED,
          center_at=theme.W // 2)

    _footer(d, [("OK", "Save"), ("ESC", "Cancel")])
    return img


def render_error(reason: str, detail: str = "") -> Image.Image:
    lines = [reason] if not detail else [reason, detail]
    return _status_page(
        badge="BT ERROR",
        badge_color=theme.AMBER,
        icon=icons.alert(28, theme.AMBER),
        title="Bluetooth problem",
        lines=lines,
        hints=[("OK", "Retry"), ("ESC", "Back")],
    )


__all__ = [
    "HomeState",
    "render_home",
    "render_pairing",
    "render_confirm",
    "render_rename",
    "render_error",
]
