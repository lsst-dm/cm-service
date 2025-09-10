"""Module implementing functions to obtain avatars from the dicebear API."""

from __future__ import annotations

from nicegui import ui

from ..lib.enum import Palette

DICEBEAR_URL = "https://api.dicebear.com/9.x"


def glass_icon(seed: str, size: int = 64) -> ui.image:
    """Fetch a dicebear "glass" avatar as a nicegui image."""
    url = f"{DICEBEAR_URL}/glass/svg?seed="
    return ui.image(f"{url}{seed}")


def identicon_icon(seed: str, size: int = 64, color: str = "transparent") -> ui.image:
    """Fetch a dicebear "identicon" avatar as a nicegui image."""
    url = f"{DICEBEAR_URL}/identicon/svg"
    url += f"?seed={seed}&rowColor={color.strip('#')}&backgroundColor={Palette.WHITE.light.strip('#')}"
    return ui.image(url)
