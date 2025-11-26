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

    def load_from_storage(self):
        favorites = self.get_favorites_set()
        if self.campaign_id in favorites:
            self.selected = True
            self.toggle_icon()

    def click(self):
        self.selected = not self.selected
        if self.selected:
            self.favorite()
        else:
            self.unfavorite()
        ui.notify(f"Favoriting {self.campaign_id}")

    def toggle_icon(self):
        if self.selected:
            self.icon = "check"
        else:
            self.icon = "bookmark"

    def get_favorites_set(self) -> set[str]:
        return app.storage.client["state"].user.favorites

    def favorite(self):
        self.selected = True
        favorites = app.storage.client["state"].user.favorites
        favorites.add(self.campaign_id)
        app.storage.client["state"].user.favorites = favorites
        self.toggle_icon()

    def unfavorite(self):
        self.selected = False
        favorites = app.storage.client["state"].user.favorites
        favorites.remove(self.campaign_id)
        app.storage.client["state"].user.favorites = favorites
        self.toggle_icon()
