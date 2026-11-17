"""Structural checks for the framebuffer screens.

These are cheap and catch layout regressions: wrong canvas, wrong accent,
badge disappearing, overlay not covering the cards.
"""

from mouse_jiggler.ui import screens, theme


def _px(img, x, y):
    return img.getpixel((x, y))


def test_canvas_and_background():
    for image in (
        screens.render_home(screens.HomeState()),
        screens.render_home(screens.HomeState(running=True)),
        screens.render_pairing(),
    ):
        assert image.size == (theme.W, theme.H)
        assert image.mode == "RGB"
        assert _px(image, 0, 0) == theme.BACKGROUND
        assert _px(image, theme.W - 1, theme.H - 1) == theme.BACKGROUND


def test_home_card_border_matches_state():
    idle = screens.render_home(screens.HomeState(selected=1))
    # 1 px accent border on the centre card's left edge
    assert _px(idle, theme.CENTER_CARD[0], 80) == theme.PRIMARY

    running = screens.render_home(screens.HomeState(selected=1, running=True))
    assert _px(running, theme.CENTER_CARD[0], 80) == theme.AMBER


def test_carousel_rotates_accent():
    by_mode = screens.render_home(screens.HomeState(selected=2))
    # Mode is centred: its accent is violet where the centre border sits
    assert _px(by_mode, theme.CENTER_CARD[0], 80) == theme.VIOLET
    # and Pair, now on the left, keeps the neutral border
    assert _px(by_mode, theme.LEFT_CARD_X, 80) == theme.BORDER


def test_rename_screen_renders():
    empty = screens.render_rename("", cursor=True, connected=False)
    filled = screens.render_rename("Desk Mouse", cursor=False)
    for image in (empty, filled):
        assert image.size == (theme.W, theme.H)
        assert image.getpixel((0, 0)) == theme.BACKGROUND


def test_rename_card_uses_pink_accent():
    image = screens.render_home(screens.HomeState(selected=3, device_name="Desk Mouse"))
    assert _px(image, theme.CENTER_CARD[0], 80) == theme.PINK


def test_status_pages_render():
    pairing = screens.render_pairing(161)
    assert _px(pairing, 160, 36) in (theme.BLUE, theme.BACKGROUND)
    error = screens.render_error("Adapter not found")
    assert error.size == (theme.W, theme.H)


def test_confirm_and_error_pages_render():
    confirm = screens.render_confirm("DESKTOP-7K2")
    error = screens.render_error("Bluetooth adapter hci0 is not available", "run as root")
    for image in (confirm, error):
        assert image.size == (theme.W, theme.H)
        assert image.getpixel((0, 0)) == theme.BACKGROUND
