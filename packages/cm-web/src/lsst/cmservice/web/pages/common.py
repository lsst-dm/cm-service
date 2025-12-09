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
    """Campaign Management Page

    Lifecycle
    ---------
    Create an instance of a subclass of this page within a route. Optionally,
    any async page setup, like data loading, can be implemented in the async
    `setup()` method before calling the page's `render()` method:

    ```
    @ui.page("/path/to/page")
    async def this_page():
        if page := await CMPage().setup():
            page.render()
    ```

    If there is no async data loading needed at page initialization, the render
    method may be called directly after creating the page instance:

    ```
    @ui.page("/path/to/page")
    def this_page():
        CMPage().render():
    ```

    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.apply_style()
        storage.initialize_client_storage()
        self.page_route: str = kwargs.pop("path", "/")
        self.page_title: str = kwargs.pop("title", "~SCENE MISSING~")
        self.breadcrumbs: list[str] = kwargs.pop("breadcrumbs", [])
        self.footers: list[str] = kwargs.pop("footers", [])
        self.kwargs = kwargs
        self.drawer_open = False
        self.page_layout()

    @staticmethod
    def apply_style() -> None:
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

    def page_layout(self) -> None:
        self.create_drawer()
        with ui.header(elevated=True).classes("shrink-0") as self.header:
            with ui.link(target="/").classes("text-white !no-underline"):
                ui.label("Campaign Management").classes("text-h4")
            ui.space()
            ui.label(self.page_title).classes("text-h4")
            ui.space()
            for crumb in self.breadcrumbs:
                ui.label(crumb).classes("text-h6")
                ui.space()
            ui.space()
            ui.button(icon="menu", on_click=lambda: self.toggle_drawer()).props("flat color=white")

        with (
            ui.column()
            .classes("flex flex-col p-0 m-0 w-full")
            .style("""
            height: calc(100vh - 72px - 66px);
        """) as self.content
        ):
            ...

        with ui.footer(bordered=True, elevated=True).classes("shrink-0") as self.footer:
            for footer in self.footers:
                ui.label(footer).classes("text-xs")

        self.overlay_div = ui.element("div").classes("hidden")

    async def setup(self) -> Any:
        """Async method called at page creation. Subpages can override this
        method to perform data loading/prep, etc., before calling render().
        """
        return self

    def render(self) -> None:
        """Method to create main content for page.

        Subclasses should use the `create_content()` method, which is called
        from within the content column's context manager.
        """
        with self.content:
            self.create_content()

    def create_drawer(self) -> None:
        with ui.right_drawer(value=None, bordered=True, elevated=True).bind_value_from(self, "drawer_open"):
            with ui.column():
                self.drawer_contents()

    def create_content(self) -> None:
        raise NotImplementedError("Pages must override this function")

    def drawer_contents(self) -> None:
        raise NotImplementedError("Pages must override this function")

    def toggle_drawer(self) -> None:
        self.drawer_open = not self.drawer_open

    def show_spinner(self, message="Loading..."):
        self.drawer_open = False
        overlay_classes = "fixed inset-0 bg-white bg-opacity-90 z-50 flex items-center justify-center"
        self.overlay_div.clear()
        self.overlay_div.classes(remove="hidden", add=overlay_classes)
        with self.overlay_div:
            with ui.column().classes("items-center"):
                ui.spinner(size="xl")
                ui.label(message).classes("text-xl mt-4")

    def hide_spinner(self):
        overlay_classes = "fixed inset-0 bg-white bg-opacity-90 z-50 flex items-center justify-center"
        self.overlay_div.classes(remove=overlay_classes, add="hidden")
        self.overlay_div.clear()
