from nicegui import ui

from ..settings import settings
from .common import CMPage


class HelpPage(CMPage):
    """A page for general help and documentation. Each section is rendered
    as a subpage. Any nested help route not associated with a specific subpage
    is served by the main help landing page instead of producing a 404 error.
    """

    def drawer_contents(self) -> None: ...

    async def create_content(self) -> None:
        with ui.button_group().classes("w-full h-[4rem]"):
            ui.button("Help", on_click=lambda: ui.navigate.to("/help"), color="secondary").classes("flex-1")
            ui.button("Step", on_click=lambda: ui.navigate.to("/help/step"), color="secondary").classes(
                "flex-1"
            )
            ui.button("BPS", on_click=lambda: ui.navigate.to("/help/bps"), color="secondary").classes(
                "flex-1"
            )
            ui.button("Butler", on_click=lambda: ui.navigate.to("/help/butler"), color="secondary").classes(
                "flex-1"
            )
            ui.button("LSST", on_click=lambda: ui.navigate.to("/help/lsst"), color="secondary").classes(
                "flex-1"
            )
            ui.button("WMS", on_click=lambda: ui.navigate.to("/help/wms"), color="secondary").classes(
                "flex-1"
            )
            ui.button("Site", on_click=lambda: ui.navigate.to("/help/site"), color="secondary").classes(
                "flex-1"
            )

        with ui.element("div").classes("w-full h-full overflow-x-hidden overflow-y-auto"):
            ui.sub_pages(
                {
                    "/help": self.landing_help,
                    "/help/step": self.step_help,
                    "/help/bps": self.bps_help,
                    "/help/butler": self.butler_help,
                    "/help/lsst": self.lsst_help,
                    "/help/wms": self.wms_help,
                    "/help/site": self.site_help,
                },
                show_404=False,
            ).classes("w-full h-full")

    async def landing_help(self) -> None:
        """The main landing page for the help page network. Served by the
        `/help` route and any `/help/*` route not otherwise associated with a
        subpage.
        """
        ui.markdown("""
        # Main Help
        Choose a help section from the options above.
        """)

        with ui.expansion(
            text="Glossary", caption="A brief glossary of terms used throughout CM Service."
        ).classes("w-full"):
            with (
                ui.element("div")
                .classes("w-full overflow-x-auto")
                .style("column-count: 2; column-gap: 2rem;")
            ):
                await self.markdown_help_section("cmglossary.md")

        with ui.expansion(
            text="Page Overview", caption="An overview of Pages available in CM Service."
        ).classes("w-full"):
            with (
                ui.element("div")
                .classes("w-full overflow-x-auto")
                .style("column-count: 2; column-gap: 2rem;")
            ):
                await self.markdown_help_section("cmpages.md")

    async def bps_help(self) -> None:
        ui.markdown("""
        # BPS Help
        """)

        await self.manifest_spec_iframe("bps")

    async def step_help(self) -> None:
        ui.markdown("""
        # Step Help
        """)

        await self.manifest_spec_iframe("step")

    async def butler_help(self) -> None:
        ui.markdown("""
        # Butler Help
        """)

        await self.manifest_spec_iframe("butler")

    async def lsst_help(self) -> None:
        ui.markdown("""
        # LSST Help
        """)

        await self.manifest_spec_iframe("lsst")

    async def wms_help(self) -> None:
        ui.markdown("""
        # WMS Help
        """)

        await self.manifest_spec_iframe("wms")

    async def site_help(self) -> None:
        ui.markdown("""
        # Site Help
        """)

        await self.manifest_spec_iframe("site")

    async def manifest_spec_iframe(self, kind: str) -> None:
        """Adds an iframe element into which is loaded the Manifest Spec html
        reference page. This page is generated from pydantic models as
        jsonschema then HTML is generated from that.
        """
        ui.element("iframe").props(f"src='/static/docs/{kind}_spec.html'").classes("w-full h-full")

    async def markdown_help_section(self, md: str) -> None:
        """Adds a markdown element with the contents of the markdown file
        referenced by the `md` argument. This file must exist in the "markdown"
        directory relative to the static content location indicated by the
        `settings.static_dir` Path.
        """

        markdown_content = (settings.static_dir / "markdown" / md).read_text()
        ui.markdown(markdown_content, sanitize=True).classes("w-full h-full")
