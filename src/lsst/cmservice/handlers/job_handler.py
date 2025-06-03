from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import async_scoped_session

from ..common.enums import ErrorActionEnum, StatusEnum
from ..common.errors import CMBadEnumError
from ..db.element import ElementMixin
from .element_handler import ElementHandler

if TYPE_CHECKING:
    from ..db import Job


class JobHandler(ElementHandler):
    """SubClass of ElementHandler to deal with job operations"""

    async def _post_check(
        self,
        session: async_scoped_session,
        element: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        # This is so mypy doesn't think we are passing in a script
        if TYPE_CHECKING:
            assert isinstance(element, Job)  # for mypy

        await session.refresh(element, attribute_names=["tasks_", "errors_"])

        requires_review = False
        is_failure = False

        for error_ in element.errors_:
            if error_.error_type_id is None:
                requires_review = True
                continue
            await session.refresh(error_, attribute_names=["error_type_"])

            error_type_ = error_.error_type_
            if error_type_.error_action is ErrorActionEnum.fail:
                is_failure = True
                break
            if error_type_.error_action is ErrorActionEnum.review:
                requires_review = True
                continue
            if error_type_.error_action is ErrorActionEnum.accept:
                continue
            raise CMBadEnumError(  # pragma: no cover
                f"Unexpected ErrorActionnEnum {error_type_.error_action}"
            )

        if is_failure:
            return StatusEnum.failed
        if requires_review:
            return StatusEnum.reviewable

        return StatusEnum.accepted
