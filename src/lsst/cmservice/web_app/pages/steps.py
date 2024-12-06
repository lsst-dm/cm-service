from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.common.enums import StatusEnum
from lsst.cmservice.db import Campaign, Step
from lsst.cmservice.web_app.utils.utils import map_status


async def get_campaign_steps(session: async_scoped_session, campaign_id: int) -> Sequence:
    q = select(Step).where(Step.parent_id == campaign_id).order_by(Step.id)
    async with session.begin_nested():
        results = await session.scalars(q)
        return results.all()


async def get_step_details(session: async_scoped_session, step: Step) -> dict:
    step_groups = await step.children(session)
    no_groups = len(list(step_groups))
    no_groups_completed = len([group for group in step_groups if group.status == StatusEnum.accepted])
    no_groups_need_attention = len(
        [group for group in step_groups if map_status(group.status) == "NEED_ATTENTION"],
    )
    no_groups_failed = len([group for group in step_groups if map_status(group.status) == "FAILED"])
    step_details = {
        "id": step.id,
        "name": step.name,
        "fullname": step.fullname,
        "status": map_status(step.status),
        "no_groups": no_groups,
        "no_groups_completed": no_groups_completed,
        "no_groups_need_attention": no_groups_need_attention,
        "no_groups_failed": no_groups_failed,
    }
    return step_details


async def get_campaign_by_id(session: async_scoped_session, campaign_id: int) -> Campaign | None:
    q = select(Campaign).where(Campaign.id == campaign_id)
    async with session.begin_nested():
        results = await session.scalars(q)
        campaign = results.first()
        return campaign
