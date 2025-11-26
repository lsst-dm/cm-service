from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from nicegui import ui

from ..components import storage
from ..lib.enum import Palette


@contextmanager
def cm_frame(navigation_title: str, breadcrumbs: list[str] = [], footers: list[str] = []) -> Generator:
    """Generates a consistent page frame and color palette assignment consist-
    ing of a header and footer. The generator yields to the caller when page
    content is ready to be added.
    """
    storage.initialize_client_storage()

    ui.colors(
        primary=Palette.BLUE.dark,
        secondary=Palette.INDIGO.dark,
        accent=Palette.VIOLET.light,
        positive=Palette.GREEN.light,
        negative=Palette.RED.light,
        info=Palette.ORANGE.light,
        warning=Palette.ORANGE.dark,
        white=Palette.WHITE.light,
        dark=Palette.BLACK.light,
        dark_page=Palette.BLACK.dark,
    )
    with ui.header(elevated=True):
        with ui.link(target="/").classes("text-white !no-underline"):
            ui.label("Campaign Management").classes("text-h4")
        ui.space()
        ui.label(navigation_title).classes("text-h4")
        ui.space()
        for crumb in breadcrumbs:
            ui.label(crumb).classes("text-h6")
            ui.space()

    yield

    with ui.footer(bordered=True, elevated=True):
        for footer in footers:
            ui.label(footer).classes("text-h6")


class CMPage:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        page_route: str = kwargs.get("path", "/")
        page_title: str = kwargs.get("title", "~SCENE MISSING~")

        @ui.page(page_route)
        def page_frame() -> None:
            with cm_frame(page_title):
                ...
