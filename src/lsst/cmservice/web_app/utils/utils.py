from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.common.enums import LevelEnum, StatusEnum
from lsst.cmservice.db import NodeMixin

# from lsst.cmservice.web_app.pages.group_details import get_group_node
# from lsst.cmservice.web_app.pages.step_details import get_step_node


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


async def update_data_dict(session: async_scoped_session, element: NodeMixin, data_dict: dict) -> NodeMixin:
    updated_element = await element.update_data_dict(session, **data_dict)
    return updated_element


async def update_collections(
    session: async_scoped_session, element: NodeMixin, collections: dict
) -> NodeMixin:
    updated_element = await element.update_collections(session, **collections)
    return updated_element


async def update_child_config(
    session: async_scoped_session, element: NodeMixin, child_config: dict
) -> NodeMixin:
    updated_element = await element.update_child_config(session, **child_config)
    return updated_element


async def get_element(session: async_scoped_session, element_id: int, element_type: int) -> NodeMixin:
    from lsst.cmservice.web_app.pages.group_details import get_group_node
    from lsst.cmservice.web_app.pages.step_details import get_step_node

    element = None
    print(f"Element ID: {element_id}, element_type: {element_type}")
    match element_type:
        case LevelEnum.step.value:
            print("It's a step")
            element = await get_step_node(session=session, step_id=element_id)
        case LevelEnum.group.value:
            print("It's a group")
            element = await get_group_node(session=session, group_id=element_id)

    return element
