from typing import Self

from httpx import AsyncClient
from nicegui import ui

from .common import CMPage


class CanvasScratchPage(CMPage):
    async def setup(self, client_: AsyncClient | None = None) -> Self:
        """Async method called at page creation. Subpages can override this
        method to perform data loading/prep, etc., before calling render().
        """
        ui.add_head_html("""<script src="/static/cm-canvas-bundle.iife.js"></script>""")
        return self

    async def create_content(self) -> None:
        with (
            ui.element("div")
            .classes("flex flex-col p-0 m-0 w-full")
            .style("height: calc(100vh - 72px - 66px);")
        ):
            self.create_campaign_canvas()

    def drawer_contents(self) -> None: ...

    def create_campaign_canvas(self) -> None:
        """A section containing a Canvas component for editing a campaign
        graph.
        """
        with (
            ui.element("div")
            .props("id=canvas-container")
            .classes("flex-1 min-h-0 w-full border-1 border-black")
        ):
            ui.run_javascript("""
                window.flowInstance = initializeFlow("canvas-container", {
                    nodes: [],
                    edges: [],
                    onClick: (data) => emitEvent("edit", data)
                });
            """)
            ui.on("edit", ui.notify)
