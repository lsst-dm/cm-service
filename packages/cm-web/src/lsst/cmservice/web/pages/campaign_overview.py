from functools import partial
from typing import Annotated

from fastapi import Depends
from httpx import AsyncClient
from nicegui import app, run, ui

from ..api.campaigns import get_campaign_summary, toggle_campaign_state
from ..components import dicebear
from ..lib.client_factory import CLIENT_FACTORY
from ..lib.enum import Palette, StatusDecorators
from .common import cm_frame


@ui.page("/")
async def campaign_overview(client_: Annotated[AsyncClient, Depends(CLIENT_FACTORY.get_aclient)]) -> None:
    campaigns = await run.io_bound(get_campaign_summary, client=client_)

    with cm_frame("Campaign Overview"):
        with ui.grid(columns="auto 4fr"):
            async for campaign in campaigns:
                campaign_id = campaign["id"]
                node_times: list[str] = []
                if app.storage.user.get(campaign_id) is None:
                    app.storage.user[campaign_id] = {}
                app.storage.user[campaign_id]["status"] = campaign["status"]

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
                        ui.label(campaign_id).classes("italic text-gray-75 font-thin")
                        ui.space()
                        ui.chip(
                            "Favorite",
                            selectable=True,
                            icon="bookmark",
                            color=Palette.ORANGE.light,
                        )
