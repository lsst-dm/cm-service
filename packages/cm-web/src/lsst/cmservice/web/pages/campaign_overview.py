from functools import partial
from typing import TYPE_CHECKING, Annotated, Self

from fastapi import Depends
from httpx import AsyncClient
from nicegui import app, run, ui
from nicegui.events import ValueChangeEventArguments

from ..api.campaigns import get_campaign_summary, toggle_campaign_state
from ..components import button, dicebear, storage
from ..lib.client_factory import CLIENT_FACTORY
from ..lib.enum import Palette, StatusDecorators
from ..settings import settings
from .common import CMPage


class CampaignOverviewPage(CMPage):
    def filter_campaign_card(self, campaign_id: str) -> bool:
        """Checks campaign against active overview client filters to determine
        whether it should be visible.
        """
        # TODO is it better to bind card visibility to this or to actually
        # filter campaigns from the page/client model states? For first contact
        # we'll do the latter
        display_campaign = True

        # if the favorites filter is active, return False if the campaign is
        # not in the user's favorites, otherwise continue to check additional
        # filters
        if self.favorites_switch.value:
            if campaign_id not in app.storage.client["state"].user.favorites:
                return False

        return display_campaign

    async def setup(self, client_: AsyncClient | None = None) -> Self:
        """Async method called at page creation. Subpages can override this
        method to perform data loading/prep, etc., before calling render().
        """
        if client_ is None:
            raise RuntimeError("Campaign Overview page setup requires an httpx client")

        self.show_spinner()
        storage.initialize_client_storage()
        client_state: storage.ClientStorageModel = app.storage.client["state"]
        self.model: dict = {
            "campaigns": {},
        }

        async for campaign in await run.io_bound(get_campaign_summary, client=client_):
            # TODO check favorites / filters
            campaign_id = campaign["id"]
            self.model["campaigns"][campaign_id] = campaign
            if client_state.campaigns.get(campaign_id) is None:
                client_state.campaigns[campaign_id] = {}
            client_state.campaigns[campaign_id]["status"] = campaign["status"]
        return self

    def campaign_card(self, campaign_id: str) -> None:
        """method to generate an overview card for a campaign"""
        if not self.filter_campaign_card(campaign_id):
            return None

        node_times: list[str] = []
        campaign = self.model["campaigns"][campaign_id]

        with ui.card():
            with ui.row():
                with ui.card_section():
                    with ui.link(target=f"/campaign/{campaign_id}"):
                        with ui.avatar(size="128px"):
                            dicebear.glass_icon(campaign_id)
                with ui.card_section():
                    with ui.row().classes("items-center"):
                        ui.chip(
                            campaign["name"],
                            color=Palette.WHITE.light,
                            icon=StatusDecorators[campaign["status"]].emoji,
                        ).classes("bold text-lg font-black").tooltip(campaign["status"])
                    with ui.row().classes("items-center"):
                        for node_status in campaign["node_summary"]:
                            status_decorator = StatusDecorators[node_status["status"]]
                            ui.chip(
                                node_status["count"],
                                icon=status_decorator.emoji,
                                color=status_decorator.color.as_named(fallback=True),
                            ).tooltip(node_status["status"])
                            node_times.append(node_status.get("mtime") or "")
                    if node_times:
                        with ui.row().classes("items-center"):
                            ui.icon("design_services")
                            ui.label(sorted(node_times)[-1])
            # card actions
            with ui.card_actions().props("align=right").classes("items-center text-sm w-full"):
                campaign_toggle = partial(toggle_campaign_state, campaign=campaign)
                campaign_running: bool = campaign["status"] == "running"
                campaign_terminal: bool = campaign["status"] in ("accepted", "failed", "rejected")
                campaign_switch = ui.switch(value=campaign_running, on_change=campaign_toggle).bind_text_from(
                    campaign, target_name="status"
                )
                campaign_switch.enabled = not campaign_terminal
                ui.space()
                button.FavoriteButton(id=campaign_id)
                with ui.fab("save_as", direction="up"):
                    clone_navigator = partial(ui.navigate.to, f"/clone/{campaign_id}")
                    export_navigator = partial(ui.notify, f"Export Campaign {campaign_id}...")
                    ui.fab_action("ios_share", label="export", on_click=export_navigator).disable()
                    ui.fab_action("copy_all", label="clone", on_click=clone_navigator)

            # card footer
            ui.label(campaign_id).classes("italic text-gray-75 font-thin")

    @ui.refreshable_method
    def create_campaign_grid(self) -> None:
        """Renders a grid of campaign cards."""
        with ui.grid(columns="auto 4fr"):
            for campaign in self.model["campaigns"]:
                self.campaign_card(campaign)

    @ui.refreshable_method
    def create_content(self) -> None:
        """The primary content-rendering method for the page, called by render
        within the column element between page header and footer.
        """
        self.create_campaign_grid()

        with ui.page_sticky(position="bottom-right", x_offset=20, y_offset=20):
            ui.button(icon="add", on_click=lambda: ui.navigate.to("/new_campaign")).props("fab color=accent")

        self.hide_spinner()

    def drawer_contents(self) -> None:
        # TODO bind to content refresh
        favorites_active = "favorites" in app.storage.client["state"].user.active_filters
        self.favorites_switch = ui.switch(
            "Favorites", value=favorites_active, on_change=self.toggle_favorites_filter
        )

        # FIXME label doesn't show when no status filters applied
        self.status_filters = ui.select(
            ["waiting", "paused", "running", "failed", "accepted", "rejected"],
            multiple=True,
            label="Filter by Status",
        ).props("use-chips")

        # TODO input field for filter by name
        ...

    async def toggle_favorites_filter(self, e: ValueChangeEventArguments) -> None:
        """Callback when favorites switch is changed."""
        if TYPE_CHECKING:
            assert isinstance(e.sender, ui.switch)

        active_filters = app.storage.client["state"].user.active_filters
        try:
            if e.sender.value:
                active_filters.add("favorites")
            else:
                active_filters.remove("favorites")
        except KeyError:
            pass
        app.storage.client["state"].user.active_filters = active_filters
        await self.create_campaign_grid.refresh()


@ui.page("/", response_timeout=settings.timeout)
async def campaign_overview_page(
    client_: Annotated[AsyncClient, Depends(CLIENT_FACTORY.get_aclient)],
) -> None:
    await ui.context.client.connected()
    if page := await CampaignOverviewPage(title="Campaign Overview").setup(client_):
        page.render()
