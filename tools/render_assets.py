#!/usr/bin/env python3
"""Render the design assets for the CardputerZero Mouse Jiggler.

    python3 tools/render_assets.py

Writes:
    docs/ui-mockup.png     ready state (Start)
    docs/ui-running.png    running state (Stop, Fast)
    docs/ui-mode.png       carousel centred on Mode (Jiggle)
    docs/ui-rename-card.png  carousel centred on Rename
    docs/ui-rename.png     name editor
    docs/ui-pairing.png    pairing status page
    assets/icon-256.png    256x256 icon, transparent glyph (docs/store)
    applaunch/share/images/mouse-jiggler.png  100x100 icon used by APPLaunch

The screens come from the real UI module (src/mouse_jiggler/ui), so these files
double as visual regression fixtures.
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from mouse_jiggler.ui import icon, screens  # noqa: E402


def main() -> None:
    outputs = {
        "docs/ui-mockup.png": screens.render_home(screens.HomeState(selected=1)),
        "docs/ui-running.png": screens.render_home(
            screens.HomeState(selected=1, running=True, mode=1,
                              elapsed="00:04:12", reports=14)
        ),
        "docs/ui-mode.png": screens.render_home(
            screens.HomeState(selected=2, running=True, mode=2,
                              elapsed="00:04:12", reports=14)
        ),
        "docs/ui-rename-card.png": screens.render_home(
            screens.HomeState(selected=3, device_name="Desk Mouse")
        ),
        "docs/ui-rename.png": screens.render_rename("Desk Mouse"),
        "docs/ui-pairing.png": screens.render_pairing(161),
        "assets/icon-256.png": icon.render_at(256),
        "applaunch/share/images/mouse-jiggler.png": icon.render(),
    }
    for rel, image in outputs.items():
        path = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        image.save(path)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
