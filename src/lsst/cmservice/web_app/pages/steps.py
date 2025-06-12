from collections.abc import Sequence

from sqlalchemy import select

from lsst.cmservice.common.enums import StatusEnum
from lsst.cmservice.common.types import AnyAsyncSession
from lsst.cmservice.db import Campaign, Step
from lsst.cmservice.parsing.string import parse_element_fullname
from lsst.cmservice.web_app.utils.utils import map_status


async def get_campaign_steps(session: AnyAsyncSession, campaign_id: int) -> Sequence:
    q = select(Step).where(Step.parent_id == campaign_id).order_by(Step.id)
    async with session.begin_nested():
        results = await session.scalars(q)
        return results.all()


async def get_step_details(session: AnyAsyncSession, step: Step) -> dict:
    step_groups = await step.children(session)
    no_groups = len(list(step_groups))
    no_groups_completed = len([group for group in step_groups if group.status is StatusEnum.accepted])
    no_groups_need_attention = len(
        [group for group in step_groups if map_status(group.status) == "NEED_ATTENTION"],
    )
    no_groups_failed = len([group for group in step_groups if map_status(group.status) == "FAILED"])
    step_details = {
        "id": step.id,
        "fullname": parse_element_fullname(step.fullname).model_dump(),
        "status": map_status(step.status),
        "org_status": {"name": step.status.name, "value": step.status.value},
        "no_groups": no_groups,
        "no_groups_completed": no_groups_completed,
        "no_groups_need_attention": no_groups_need_attention,
        "no_groups_failed": no_groups_failed,
        "level": step.level.value,
    }
    return step_details


async def get_campaign_by_id(session: AnyAsyncSession, campaign_id: int) -> Campaign | None:
    q = select(Campaign).where(Campaign.id == campaign_id)
    async with session.begin_nested():
        results = await session.scalars(q)
        campaign = results.first()
        return campaign
