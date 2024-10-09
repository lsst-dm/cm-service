from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pause
from sqlalchemy import JSON, DateTime
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from ..common.enums import LevelEnum
from ..common.errors import CMBadEnumError
from .base import Base
from .campaign import Campaign
from .element import ElementMixin
from .group import Group
from .job import Job
from .node import NodeMixin
from .step import Step


class Queue(Base, NodeMixin):
    """Database table to implement processing queue"""

    __tablename__ = "queue"
    class_string = "queue"

    id: Mapped[int] = mapped_column(primary_key=True)
    time_created: Mapped[datetime] = mapped_column(type_=DateTime)
    time_updated: Mapped[datetime] = mapped_column(type_=DateTime)
    time_finished: Mapped[datetime | None] = mapped_column(type_=DateTime, default=None)
    time_next_check: Mapped[datetime | None] = mapped_column(type_=DateTime, default=datetime.min)
    interval: Mapped[float] = mapped_column(default=300.0)
    options: Mapped[dict | list | None] = mapped_column(type_=JSON)

    c_id: Mapped[int | None] = mapped_column(ForeignKey("campaign.id", ondelete="CASCADE"), index=True)
    s_id: Mapped[int | None] = mapped_column(ForeignKey("step.id", ondelete="CASCADE"), index=True)
    g_id: Mapped[int | None] = mapped_column(ForeignKey("group.id", ondelete="CASCADE"), index=True)
    j_id: Mapped[int | None] = mapped_column(ForeignKey("job.id", ondelete="CASCADE"), index=True)

    c_: Mapped[Campaign] = relationship("Campaign")
    s_: Mapped[Step] = relationship("Step")
    g_: Mapped[Group] = relationship("Group")
    j_: Mapped[Job] = relationship("Job")

    col_names_for_table = [
        "id",
        "interval",
        "time_created",
        "time_updated",
        "time_finished",
        "time_next_check",
    ]

    def __init__(self, element, time_created, time_updated, time_finished=None):
        self.time_created = time_created
        self.time_updated = time_updated
        self.time_finished = time_finished

        if isinstance(element, Campaign):
            self.c_ = element
        elif isinstance(element, Step):
            self.s_ = element
        elif isinstance(element, Group):
            self.g_ = element
        elif isinstance(element, Job):
            self.j_ = element
        else:
            assert ValueError

    def get_element_level(self):
        if self.c_:
            return LevelEnum.campaign
        elif self.s_:
            return LevelEnum.step
        elif self.g_:
            return LevelEnum.group
        elif self.j_:
            return LevelEnum.job
        else:
            assert ValueError

    async def get_element(
        self,
    ) -> ElementMixin:
        """Get the parent `Element`

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        element : ElementMixin
            Requested Parent Element
        """
        if self.c_:
            return self.c_
        elif self.s_:
            return self.s_
        elif self.g_:
            return self.g_
        elif self.j_:
            return self.j_
        else:
            raise ValueError

    @classmethod
    async def get_create_kwargs(
        cls,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> dict:
        fullname = kwargs["fullname"]
        element_level = LevelEnum.get_level_from_fullname(fullname)
        now = datetime.now()
        ret_dict = {
            "element_level": element_level,
            "time_created": now,
            "time_updated": now,
            "options": kwargs.get("options", {}),
        }

        element: ElementMixin | None = None
        if element_level == LevelEnum.campaign:
            element = await Campaign.get_row_by_fullname(session, fullname)
            ret_dict["c_id"] = element.id
        elif element_level == LevelEnum.step:
            element = await Step.get_row_by_fullname(session, fullname)
            ret_dict["s_id"] = element.id
        elif element_level == LevelEnum.group:
            element = await Group.get_row_by_fullname(session, fullname)
            ret_dict["g_id"] = element.id
        elif element_level == LevelEnum.job:
            element = await Job.get_row_by_fullname(session, fullname)
            ret_dict["j_id"] = element.id
        else:  # pragma: no cover
            raise CMBadEnumError(f"Bad level for queue: {element_level}")

        ret_dict["element_id"] = element.id
        return ret_dict

    async def element_sleep_time(
        self,
        session: async_scoped_session,
    ) -> int:
        """Check how long to sleep based on what is running"""
        element = await self.get_element()
        return await element.estimate_sleep_time(session)

    def waiting(
        self,
    ) -> bool:
        """Check if this the Queue Element is done waiting

        Returns
        -------
        done: bool
            Returns True if still waiting
        """
        delta_t = timedelta(seconds=self.interval)
        next_check = self.time_updated + delta_t
        now = datetime.now()
        return now < next_check

    def pause_until_next_check(
        self,
        estimated_wait_time: int,
    ) -> None:  # pragma: no cover
        """Sleep until the next time check"""
        wait_time = min(estimated_wait_time, self.interval)
        delta_t = timedelta(seconds=wait_time)
        next_check = self.time_updated + delta_t
        now = datetime.now()
        if now < next_check:
            pause.until(next_check)

    async def _process_and_update(
        self,
        session: async_scoped_session,
    ) -> bool:  # pragma: no cover
        """Process associated element and update queue row"""
        element = await self.get_element()
        if not element.status.is_processable_element():
            return False

        process_kwargs: dict = {}
        if isinstance(self.options, dict):
            process_kwargs.update(**self.options)
        (_changed, status) = await element.process(session, **process_kwargs)
        # FIXME, use _chagned to retry
        now = datetime.now()
        update_dict = {"time_updated": now}
        if status.is_successful_element():
            update_dict.update(time_finished=now)

        await self.update_values(session, **update_dict)
        return element.status.is_processable_element()

    async def process_element(
        self,
        session: async_scoped_session,
    ) -> bool:  # pragma: no cover
        """Process associated element"""
        return await self._process_and_update(session)

    async def process_element_loop(
        self,
        session: async_scoped_session,
    ) -> None:  # pragma: no cover
        """Process associated element until it is done or requires
        intervention
        """
        can_continue = True
        while can_continue:
            estimated_wait_time = await self.element_sleep_time(session)
            self.pause_until_next_check(estimated_wait_time)
            can_continue = await self._process_and_update(session)
