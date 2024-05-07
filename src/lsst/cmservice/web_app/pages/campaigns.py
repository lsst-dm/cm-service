from sqlalchemy import select

from lsst.cmservice.db import Campaign, Group
from lsst.cmservice.common.enums import StatusEnum


async def get_campaign_details(session, campaign):
    collections = await campaign.resolve_collections(session)
    groups = await get_campaign_groups(session, campaign)
    no_groups_completed = len([group for group in groups if group.status == StatusEnum.accepted])
    need_attention_groups = filter(
        lambda group: map_status(group.status) in ["NEED_ATTENTION", "FAILED"],
        groups,
    )
    scripts = await campaign.get_scripts(session)
    no_scripts_completed = len([script for script in scripts if script.status == StatusEnum.accepted])
    # steps = await campaign.children(session)
    # for s in steps:
    #     print(f"{s.id} - {s.name} - {s.status}")
    campaign_details = {
        "name": campaign.name,
        "lsst_version": campaign.data["lsst_version"],
        "root": collections["root"],
        "source": collections["campaign_source"],
        "status": map_status(campaign.status),
        "groups_completed": f"{no_groups_completed} of {len(groups)} groups completed",
        "scripts_completed": f"{no_scripts_completed} of {len(scripts)} scripts completed",
        "need_attention_groups": need_attention_groups,
    }
    return campaign_details


def map_status(status):
    match status:
        case StatusEnum.failed | StatusEnum.rejected:
            return "FAILED"
        case StatusEnum.paused:
            return "NEED_ATTENTION"
        case StatusEnum.running | StatusEnum.waiting | StatusEnum.ready:
            return "IN_PROGRESS"
        case StatusEnum.accepted | StatusEnum.reviewable:
            return "COMPLETE"


async def search_campaigns(session, search_term):
    q = select(Campaign).where(Campaign.name.contains(search_term))
    async with session.begin_nested():
        results = await session.scalars(q)
        return results.all()


async def get_campaign_groups(session, campaign):
    q = select(Group).where(Group.c_ == campaign)
    async with session.begin_nested():
        results = await session.scalars(q)
        return results.all()
