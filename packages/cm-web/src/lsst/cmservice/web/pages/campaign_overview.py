from functools import partial
from typing import Annotated

from fastapi import Depends
from httpx import AsyncClient
from nicegui import app, run, ui

from ..api.campaigns import get_campaign_summary, toggle_campaign_state
from ..components import button, dicebear, storage
from ..lib.client_factory import CLIENT_FACTORY
from ..lib.enum import Palette, StatusDecorators
from ..settings import settings
from .common import cm_frame


# TODO the root page should focus on client session setup and then load the
# overview as a subpage.
@ui.page("/", response_timeout=settings.timeout)
async def campaign_overview(client_: Annotated[AsyncClient, Depends(CLIENT_FACTORY.get_aclient)]) -> None:
    await ui.context.client.connected()
    storage.initialize_client_storage()

    client_state: storage.ClientStorageModel = app.storage.client["state"]
    campaigns = await run.io_bound(get_campaign_summary, client=client_)

    with cm_frame("Campaign Overview"):
        with ui.grid(columns="auto 4fr"):
            async for campaign in campaigns:
                campaign_id = campaign["id"]
                node_times: list[str] = []
                if client_state.campaigns.get(campaign_id) is None:
                    client_state.campaigns[campaign_id] = {}
                client_state.campaigns[campaign_id]["status"] = campaign["status"]

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

                    with ui.card_actions().props("align=right").classes("items-center text-sm w-full"):
                        campaign_toggle = partial(toggle_campaign_state, campaign=campaign)
                        campaign_running: bool = campaign["status"] == "running"
                        campaign_terminal: bool = campaign["status"] in ("accepted", "failed", "rejected")
                        campaign_switch = ui.switch(
                            value=campaign_running, on_change=campaign_toggle
                        ).bind_text_from(campaign, target_name="status")
                        campaign_switch.enabled = not campaign_terminal
                        ui.space()
                        button.FavoriteButton(id=campaign_id)
                        with ui.fab("save_as", direction="up"):
                            clone_navigator = partial(ui.navigate.to, f"/clone/{campaign_id}")
                            export_navigator = partial(ui.notify, f"Export Campaign {campaign_id}...")
                            ui.fab_action("ios_share", label="export", on_click=export_navigator).disable()
                            ui.fab_action("copy_all", label="clone", on_click=clone_navigator)
                    ui.label(campaign_id).classes("italic text-gray-75 font-thin")
        with ui.page_sticky(position="bottom-right", x_offset=20, y_offset=20):
            ui.button(icon="add", on_click=lambda: ui.navigate.to("/new_campaign")).props("fab color=accent")
