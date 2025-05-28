from collections.abc import Sequence
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.common.timestamp import iso_timestamp
from lsst.cmservice.db import Campaign, Group
from lsst.cmservice.web_app.pages.steps import get_campaign_steps, get_step_details
from lsst.cmservice.web_app.utils.utils import map_status


async def get_campaign_details(session: async_scoped_session, campaign: Campaign) -> dict:
    if TYPE_CHECKING:
        assert isinstance(campaign.data, dict)
    collections = await campaign.resolve_collections(session, throw_overrides=False)
    steps = await get_campaign_steps(session, campaign.id)
    campaign_steps = [await get_step_details(session, step) for step in steps]
    need_attention_steps = [step for step in campaign_steps if step["status"] in ["NEED_ATTENTION", "FAILED"]]
    in_progress_steps = [step for step in campaign_steps if step["status"] == "IN_PROGRESS"]
    complete_steps = [step for step in campaign_steps if step["status"] == "COMPLETE"]
    groups = await get_campaign_groups(session, campaign)
    need_attention_groups = [
        group for group in groups if map_status(group.status) in ["NEED_ATTENTION", "FAILED"]
    ]
    scripts = await campaign.get_all_scripts(session)
    need_attention_scripts = [
        script for script in scripts if map_status(script.status) in ["NEED_ATTENTION", "FAILED"]
    ]
    last_updated = (
        campaign.metadata_.get("mtime")
        if campaign.metadata_.get("mtime") is not None
        else campaign.metadata_.get("crtime")
    )
    campaign_details = {
        "id": campaign.id,
        "name": campaign.name,
        "last_updated": iso_timestamp(last_updated) if last_updated is not None else "",
        "lsst_version": campaign.data["lsst_version"],
        "source": collections.get("campaign_source", ""),
        "status": map_status(campaign.status),
        "org_status": {"name": campaign.status.name, "value": campaign.status.value},
        "need_attention_steps": need_attention_steps,
        "complete_steps": complete_steps,
        "in_progress_steps": in_progress_steps,
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
