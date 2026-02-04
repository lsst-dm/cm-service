"""Module for Nicegui pages.

Each module that adds page routes to the nicegui application should be imported
here to ensure that the complete application takes form on startup.

Note: Any module that adds pages or routes should not have a `from __future__
import annotations` line, as this may interfere with certain runtime type
resolution mechanisms in NiceGUI and/or FastAPI.
"""

from typing import Annotated

from fastapi import Depends
from httpx import AsyncClient
from nicegui import ui

from ..lib.client_factory import CLIENT_FACTORY
from ..settings import settings
from .campaign_detail import CampaignDetailPage
from .campaign_edit import CampaignClonePage, CampaignEditPage
from .campaign_overview import CampaignOverviewPage
from .canvas import CanvasScratchPage
from .node_detail import NodeDetailPage


@ui.page("/", response_timeout=settings.timeout)
async def campaign_overview_page(
    client_: Annotated[AsyncClient, Depends(CLIENT_FACTORY.get_aclient)],
) -> None:
    await ui.context.client.connected()
    if page := await CampaignOverviewPage(title="Campaign Overview").setup(client_):
        await page.render()


@ui.page("/campaign/{campaign_id}", response_timeout=settings.timeout)
async def campaign_detail_page(
    campaign_id: str, client_: Annotated[AsyncClient, Depends(CLIENT_FACTORY.get_aclient)]
) -> None:
    """Builds a campaign detail page"""
    if page := await CampaignDetailPage(title="Campaign Detail").setup(client_, campaign_id=campaign_id):
        await ui.context.client.connected()
        await page.render()


@ui.page("/node/{node_id}", response_timeout=settings.timeout)
async def node_detail_page(
    node_id: str, client_: Annotated[AsyncClient, Depends(CLIENT_FACTORY.get_aclient)]
) -> None:
    """Builds a node detail page"""
    if page := await NodeDetailPage(title="Node Detail").setup(client_, node_id=node_id):
        await ui.context.client.connected()
        await page.render()


@ui.page("/new_campaign", response_timeout=settings.timeout)
async def campaign_edit() -> None:
    if page := await CampaignEditPage(title="New Campaign").setup():
        await ui.context.client.connected()
        await page.render()


@ui.page("/clone/{campaign_id}", response_timeout=settings.timeout)
async def campaign_clone(campaign_id: str) -> None:
    if page := await CampaignClonePage(title="Cloned Campaign").setup(clone_campaign_model_from=campaign_id):
        await ui.context.client.connected()
        await page.render()


@ui.page("/canvas", response_timeout=settings.timeout)
async def canvas_scratch_page() -> None:
    if page := await CanvasScratchPage(title="Canvas Scratch Pad").setup():
        await ui.context.client.connected()
        await page.render()
