from __future__ import annotations

from typing import Any, Self, TypedDict, cast

from httpx import AsyncClient
from nicegui import ui

from ..components import storage
from ..lib.enum import Palette, StatusDecorators


class CMPageModel(TypedDict): ...


class CMPage[PageModelT: CMPageModel]:
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

    model: PageModelT

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
            # Custom, Alt, and Deep Colors
            red=Palette.RED.light,
            deepred=Palette.RED.dark,
            orange=Palette.ORANGE.light,
            deeporange=Palette.ORANGE.dark,
            yellow=Palette.YELLOW.light,
            deepyellow=Palette.YELLOW.dark,
            green=Palette.GREEN.light,
            deepgreen=Palette.GREEN.dark,
            blue=Palette.BLUE.light,
            deepblue=Palette.BLUE.dark,
            indigo=Palette.INDIGO.light,
            deepindigo=Palette.INDIGO.dark,
            violet=Palette.VIOLET.light,
            deepviolet=Palette.VIOLET.dark,
            # Custom Colors for Statuses
            **{status.name: status.hex for status in StatusDecorators},
        )

    @ui.refreshable_method
    def create_header(self) -> None:
        with ui.link(target="/").classes("text-white !no-underline"):
            ui.label("Campaign Management").classes("text-h4")
        ui.space()
        ui.label(self.page_title).classes("text-h5")
        ui.space()
        for crumb in self.breadcrumbs:
            ui.label(crumb).classes("text-h6")
            ui.space()
        ui.space()
        ui.button(icon="menu", on_click=lambda: self.toggle_drawer()).props("flat color=white")

    async def footer_contents(self) -> None:
        """Hook method for subclasses to implement their own footer objects"""
        pass

    def page_layout(self) -> None:
        self.create_drawer()
        with ui.header(elevated=True).classes(
            "h-[4rem] min-h-[4rem] items-center justify-between px-4 p-0"
        ) as self.header:
            self.create_header()

        # NOTE the height of this content column ==
        #      (100vh - (header + footer) - ~1.5(--nicegui-default-padding))
        with ui.column().classes(
            "h-[calc(100vh-7.5rem)] min-h-[4rem] overflow-hidden p-0 m-0 w-full"
        ) as self.content:
            pass

        self.footer = ui.footer(bordered=False, elevated=True).classes(
            "h-[2rem] min-h-[2rem] items-center justify-between px-4 p-0"
        )

        self.overlay_div = ui.element("div").classes("hidden")

    async def setup(self, client_: AsyncClient | None = None) -> Self:
        """Async method called at page creation. Subpages can override this
        method to perform data loading/prep, etc., before calling render().
        """
        self.model = cast(PageModelT, {})
        return self

    async def render(self) -> None:
        """Method to create main content for page.

        Subclasses should use the `create_content()` method, which is called
        from within the content column's context manager.
        """
        with self.footer:
            with ui.row().classes("items-center gap-2"):
                for footer in self.footers:
                    ui.label(footer).classes("text-xs m-0")
                await self.footer_contents()

            with ui.row().classes("items-center gap-2"):
                ui.button(icon="help_outline", on_click=lambda: ui.navigate.to("/help")).classes(
                    "text-white bg-info m-0"
                ).props("flat round size=sm")

        with self.content:
            await self.create_content()

    def create_drawer(self) -> None:
        with ui.right_drawer(value=None, bordered=True, elevated=True).bind_value_from(self, "drawer_open"):
            with ui.column().classes("w-full"):
                self.drawer_contents()

    async def create_content(self) -> None:
        raise NotImplementedError("Pages must override this function")

    def drawer_contents(self) -> None:
        raise NotImplementedError("Pages must override this function")

    def toggle_drawer(self) -> None:
        self.drawer_open = not self.drawer_open

    def show_spinner(self, message: str = "Loading...") -> None:
        self.drawer_open = False
        overlay_classes = "fixed inset-0 bg-white bg-opacity-90 z-50 flex items-center justify-center"
        self.overlay_div.clear()
        self.overlay_div.classes(remove="hidden", add=overlay_classes)
        with self.overlay_div:
            with ui.column().classes("items-center"):
                ui.spinner(size="xl")
                ui.label(message).classes("text-xl mt-4")

    def hide_spinner(self) -> None:
        overlay_classes = "fixed inset-0 bg-white bg-opacity-90 z-50 flex items-center justify-center"
        self.overlay_div.classes(remove=overlay_classes, add="hidden")
        self.overlay_div.clear()
