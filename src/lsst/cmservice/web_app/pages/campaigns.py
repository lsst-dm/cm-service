from collections.abc import Sequence
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.common.enums import LevelEnum, StatusEnum
from lsst.cmservice.db import Campaign, Group
from lsst.cmservice.web_app.utils.utils import map_status


async def get_campaign_details(session: async_scoped_session, campaign: Campaign) -> dict:
    if TYPE_CHECKING:
        assert isinstance(campaign.data, dict)
    collections = await campaign.resolve_collections(session, throw_overrides=False)
    groups = await get_campaign_groups(session, campaign)
    no_groups_completed = len([group for group in groups if group.status is StatusEnum.accepted])
    need_attention_groups = [
        group for group in groups if map_status(group.status) in ["NEED_ATTENTION", "FAILED"]
    ]
    scripts = await campaign.get_all_scripts(session)
    no_scripts_completed = len([script for script in scripts if script.status is StatusEnum.accepted])
    need_attention_scripts = [
        script for script in scripts if map_status(script.status) in ["NEED_ATTENTION", "FAILED"]
    ]

    campaign_details = {
        "id": campaign.id,
        "name": campaign.name,
        # FIXME use ..common.parsing.string.parse_element_fullname instead of
        #       token-counting
        "production_name": campaign.fullname.split("/")[0],
        "fullname": campaign.fullname,
        "lsst_version": campaign.data["lsst_version"],
        "source": collections.get("campaign_source", ""),
        "status": map_status(campaign.status),
        "groups_completed": f"{no_groups_completed} of {len(groups)} groups completed",
        "scripts_completed": f"{no_scripts_completed} of {len(scripts)} scripts completed",
        "need_attention_groups": need_attention_groups,
        "need_attention_scripts": need_attention_scripts,
        "level": LevelEnum.campaign.value,
        "collections": collections,
        "data": campaign.data,
        "child_config": campaign.child_config,
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
