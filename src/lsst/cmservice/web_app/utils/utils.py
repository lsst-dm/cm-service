from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.common.enums import StatusEnum
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


async def update_data_dict(session: async_scoped_session, element: NodeMixin, data_dict: dict) -> NodeMixin:
    updated_element = await element.update_data_dict(session, **data_dict)
    return updated_element
