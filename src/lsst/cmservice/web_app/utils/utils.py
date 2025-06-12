from lsst.cmservice.common.enums import LevelEnum, StatusEnum
from lsst.cmservice.common.types import AnyAsyncSession
from lsst.cmservice.db import NodeMixin


def map_status(status: StatusEnum) -> str | None:
    match status:
        case StatusEnum.failed | StatusEnum.rejected:
            return "FAILED"
        case StatusEnum.paused:
            return "NEED_ATTENTION"
        case StatusEnum.running | StatusEnum.waiting | StatusEnum.ready:
            return "IN_PROGRESS"
        case StatusEnum.accepted | StatusEnum.reviewable:
            return "COMPLETE"
    return None


async def update_data_dict(session: AnyAsyncSession, element: NodeMixin, data_dict: dict) -> NodeMixin:
    updated_element = await element.update_data_dict(session, **data_dict)
    return updated_element


async def update_collections(session: AnyAsyncSession, element: NodeMixin, collections: dict) -> NodeMixin:
    updated_element = await element.update_collections(session, **collections)
    return updated_element


async def update_child_config(session: AnyAsyncSession, element: NodeMixin, child_config: dict) -> NodeMixin:
    updated_element = await element.update_child_config(session, **child_config)
    return updated_element


async def get_element(session: AnyAsyncSession, element_id: int, element_type: int) -> NodeMixin | None:
    from lsst.cmservice.web_app.pages.group_details import get_group_node
    from lsst.cmservice.web_app.pages.job_details import get_job_node
    from lsst.cmservice.web_app.pages.script_details import get_script_node
    from lsst.cmservice.web_app.pages.step_details import get_step_node

    element = None
    match element_type:
        case LevelEnum.step.value:
            element = await get_step_node(session=session, step_id=element_id)
        case LevelEnum.group.value:
            element = await get_group_node(session=session, group_id=element_id)
        case LevelEnum.job.value:
            element = await get_job_node(session=session, job_id=element_id)
        case LevelEnum.script.value:
            element = await get_script_node(session=session, script_id=element_id)

    return element
