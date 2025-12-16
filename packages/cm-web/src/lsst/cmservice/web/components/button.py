"""Module for building UI buttons."""

from nicegui import app, ui

from ..lib.enum import Palette


class FavoriteButton(ui.button):
    def __init__(self, *, id: str, icon: str = "bookmark", **kwargs: dict):
        self.selected = False
        self.campaign_id = id
        self.storage_key = "favorites"
        super().__init__(icon=icon, color=Palette.ORANGE.light, on_click=self.click)
        self.props("fab")
        self.load_from_storage()

    def load_from_storage(self) -> None:
        favorites = self.get_favorites_set()
        if self.campaign_id in favorites:
            self.selected = True
            self.toggle_icon()

    def click(self) -> None:
        self.selected = not self.selected
        if self.selected:
            self.favorite()
        else:
            self.unfavorite()

    def toggle_icon(self) -> None:
        if self.selected:
            self.icon = "check"
        else:
            self.icon = "bookmark"

    def get_favorites_set(self) -> set[str]:
        return app.storage.client["state"].user.favorites

    def favorite(self) -> None:
        self.selected = True
        favorites = app.storage.client["state"].user.favorites
        favorites.add(self.campaign_id)
        app.storage.client["state"].user.favorites = favorites
        self.toggle_icon()

    def unfavorite(self) -> None:
        self.selected = False
        favorites = app.storage.client["state"].user.favorites
        favorites.remove(self.campaign_id)
        app.storage.client["state"].user.favorites = favorites
        self.toggle_icon()


class ToggleButton(ui.button):
    """Custom button for representing a toggleable state."""

    def __init__(self, *args, **kwargs) -> None:
        self._state = False
        self._state_icons = {
            True: kwargs.pop("on_icon", "check_box"),
            False: kwargs.pop("off_icon", "check_box_outline_blank"),
        }
        super().__init__(*args, **kwargs)
        self.on("click", self.toggle)

    def toggle(self) -> None:
        """Toggles the button between two states"""
        self._state = not self._state
        self.update()

    def update(self) -> None:
        with self.props.suspend_updates():
            self.icon = self._state_icons[self._state]
            if self._state:
                ...
            else:
                ...
        super().update()
