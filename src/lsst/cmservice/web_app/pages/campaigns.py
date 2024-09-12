from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.db import Campaign, Group
from lsst.cmservice.common.enums import StatusEnum
from lsst.cmservice.web_app.utils.utils import map_status


async def get_campaign_details(session: async_scoped_session, campaign: Campaign) -> dict:
    collections = await campaign.resolve_collections(session)
    groups = await get_campaign_groups(session, campaign)
    no_groups_completed = len([group for group in groups if group.status == StatusEnum.accepted])
    need_attention_groups = [
        group for group in groups if map_status(group.status) in ["NEED_ATTENTION", "FAILED"]
    ]
    scripts = await campaign.get_all_scripts(session)
    no_scripts_completed = len([script for script in scripts if script.status == StatusEnum.accepted])
    need_attention_scripts = [
        script for script in scripts if map_status(script.status) in ["NEED_ATTENTION", "FAILED"]
    ]

    campaign_details = {
        "id": campaign.id,
        "name": campaign.name,
        "lsst_version": campaign.data["lsst_version"],
        "out": collections["out"],
        "source": collections.get("campaign_source", ""),
        "status": map_status(campaign.status),
        "groups_completed": f"{no_groups_completed} of {len(groups)} groups completed",
        "scripts_completed": f"{no_scripts_completed} of {len(scripts)} scripts completed",
        "need_attention_groups": need_attention_groups,
        "need_attention_scripts": need_attention_scripts,
    }
    return campaign_details


async def search_campaigns(session: async_scoped_session, search_term: str) -> Sequence:
    q = select(Campaign).where(Campaign.name.contains(search_term))
    async with session.begin_nested():
        results = await session.scalars(q)
        return results.all()


async def get_campaign_groups(session: async_scoped_session, campaign: Campaign) -> Sequence:
    q = select(Group).where(Group.c_ == campaign)
    async with session.begin_nested():
        results = await session.scalars(q)
        return results.all()


async def get_all_campaigns(session: async_scoped_session) -> Sequence:
    q = select(Campaign)
    async with session.begin_nested():
        results = await session.scalars(q)
        return results.all()
