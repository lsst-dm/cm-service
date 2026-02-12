"""Module for building UI buttons."""

from typing import Any

from nicegui import app, ui

from ..lib.enum import Palette


class FavoriteButton(ui.button):
    def __init__(self, *, icon: str = "bookmark", **kwargs: Any):
        self.selected = False
        self.object_id = kwargs.get("id")
        self.storage_key = "favorites"
        super().__init__(icon=icon, color=Palette.ORANGE.light, on_click=self.click)
        self.props("flat round size=sm")
        self.load_from_storage()
        self.refreshable: ui.refreshable | None = kwargs.get("refreshable")

    def load_from_storage(self) -> None:
        favorites = self.get_favorites_set()
        if self.object_id in favorites:
            self.selected = True
        self.toggle_icon()

    async def click(self) -> None:
        self.selected = not self.selected
        if self.selected:
            self.favorite()
        else:
            self.unfavorite()
        if self.refreshable is not None:
            await self.refreshable.refresh()

    def toggle_icon(self) -> None:
        if self.selected:
            self.icon = "check"
            self.tooltip("Un-Favorite campaign")
        else:
            self.icon = "bookmark"
            self.tooltip("Favorite campaign")

    def get_favorites_set(self) -> set[str]:
        return app.storage.client["state"].user.favorites

    def favorite(self) -> None:
        self.selected = True
        favorites = app.storage.client["state"].user.favorites
        favorites.add(self.object_id)
        app.storage.client["state"].user.favorites = favorites
        self.toggle_icon()

    def unfavorite(self) -> None:
        self.selected = False
        favorites = app.storage.client["state"].user.favorites
        favorites.remove(self.object_id)
        app.storage.client["state"].user.favorites = favorites
        self.toggle_icon()


class ToggleButton(ui.button):
    """Custom button for representing a toggleable state."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
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


class TrashButton(ui.button):
    def __init__(self, *, icon: str = "delete", **kwargs: Any):
        self.selected = False
        self.object_id = kwargs.get("id")
        self.refreshable: ui.refreshable | None = kwargs.get("refreshable")
        self.storage_key = "ignore_list"
        super().__init__(icon=icon, color=Palette.WHITE.light, on_click=self.click)
        self.props("flat round size=sm")
        self.classes("text-xs")
        self.load_from_storage()

    def load_from_storage(self) -> None:
        favorites = self.get_favorites_set()
        if self.object_id in favorites:
            self.selected = True
            self.toggle_icon()

    async def click(self) -> None:
        self.selected = not self.selected
        if self.selected:
            self.favorite()
        else:
            self.unfavorite()
        if self.refreshable is not None:
            await self.refreshable.refresh()

    def toggle_icon(self) -> None:
        if self.selected:
            self.icon = "visibility_off"
            self.tooltip("Show campaign")
        else:
            self.icon = "delete"
            self.tooltip("Hide campaign")

    def get_favorites_set(self) -> set[str]:
        return app.storage.client["state"].user.ignore_list

    def unfavorite(self) -> None:
        """Remove the id from the user storage key set"""
        favorites = app.storage.client["state"].user.ignore_list
        favorites.remove(self.object_id)
        app.storage.client["state"].user.ignore_list = favorites
        self.toggle_icon()

    def favorite(self) -> None:
        """Add the id to the user storage key set"""
        favorites = app.storage.client["state"].user.ignore_list
        favorites.add(self.object_id)
        app.storage.client["state"].user.ignore_list = favorites
        self.toggle_icon()
