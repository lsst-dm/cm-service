from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pause
from fastapi import HTTPException
from sqlalchemy import JSON, DateTime, and_, select
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from ..common.enums import LevelEnum
from .base import Base
from .campaign import Campaign
from .dbid import DbId
from .element import ElementMixin
from .enums import SqlLevelEnum
from .group import Group
from .job import Job
from .node import NodeMixin
from .step import Step


class Queue(Base, NodeMixin):
    """Database table to implement processing queue"""

    __tablename__ = "queue"

    id: Mapped[int] = mapped_column(primary_key=True)
    time_created: Mapped[datetime] = mapped_column(type_=DateTime)
    time_updated: Mapped[datetime] = mapped_column(type_=DateTime)
    time_finished: Mapped[datetime | None] = mapped_column(type_=DateTime, default=None)
    interval: Mapped[float] = mapped_column(default=300.0)
    options: Mapped[dict | list | None] = mapped_column(type_=JSON)

    element_level: Mapped[LevelEnum] = mapped_column(type_=SqlLevelEnum)
    element_id: Mapped[int] = mapped_column()
    c_id: Mapped[int | None] = mapped_column(ForeignKey("campaign.id", ondelete="CASCADE"), index=True)
    s_id: Mapped[int | None] = mapped_column(ForeignKey("step.id", ondelete="CASCADE"), index=True)
    g_id: Mapped[int | None] = mapped_column(ForeignKey("group.id", ondelete="CASCADE"), index=True)
    j_id: Mapped[int | None] = mapped_column(ForeignKey("job.id", ondelete="CASCADE"), index=True)

    c_: Mapped[Campaign] = relationship("Campaign", viewonly=True)
    s_: Mapped[Step] = relationship("Step", viewonly=True)
    g_: Mapped[Group] = relationship("Group", viewonly=True)
    j_: Mapped[Job] = relationship("Job", viewonly=True)

    col_names_for_table = [
        "id",
        # "element_level",
        "element_id",
        "interval",
        "time_created",
        "time_updated",
        "time_finished",
    ]

    @hybrid_property
    def element_db_id(self) -> DbId:
        """Returns DbId"""
        return DbId(self.element_level, self.element_id)

    async def get_element(
        self,
        session: async_scoped_session,
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
        async with session.begin_nested():
            element: ElementMixin | None = None
            if self.element_level == LevelEnum.campaign:
                await session.refresh(self, attribute_names=["c_"])
                element = self.c_
            elif self.element_level == LevelEnum.step:
                await session.refresh(self, attribute_names=["s_"])
                element = self.s_
            elif self.element_level == LevelEnum.group:
                await session.refresh(self, attribute_names=["g_"])
                element = self.g_
            elif self.element_level == LevelEnum.job:
                await session.refresh(self, attribute_names=["j_"])
                element = self.j_
            else:
                raise ValueError(f"Bad level for script: {self.element_level}")
            return element

    @classmethod
    async def get_queue_item(
        cls,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> Queue:
        fullname = kwargs["fullname"]
        element_level = LevelEnum.get_level_from_fullname(fullname)
        element: ElementMixin | None = None
        if element_level == LevelEnum.campaign:
            element = await Campaign.get_row_by_fullname(session, fullname)
        elif element_level == LevelEnum.step:
            element = await Step.get_row_by_fullname(session, fullname)
        elif element_level == LevelEnum.group:
            element = await Group.get_row_by_fullname(session, fullname)
        elif element_level == LevelEnum.job:
            element = await Job.get_row_by_fullname(session, fullname)
        else:
            raise ValueError(f"Bad level for queue: {element_level}")
        query = select(cls).where(
            and_(
                cls.element_level == element_level,
                cls.element_id == element.id,
            ),
        )
        async with session.begin_nested():
            rows = await session.scalars(query)
            row = rows.first()
            if row is None:
                raise HTTPException(status_code=404, detail=f"{cls} {element_level} {element.id} not found")
            return row

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
        else:
            raise ValueError(f"Bad level for queue: {element_level}")

        ret_dict["element_id"] = element.id
        return ret_dict

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
    ) -> None:
        """Sleep until the next time check"""
        delta_t = timedelta(seconds=self.interval)
        next_check = self.time_updated + delta_t
        now = datetime.now()
        if now < next_check:
            pause.until(next_check)

    async def _process_and_update(
        self,
        session: async_scoped_session,
    ) -> bool:
        element = await self.get_element(session)
        if not element.status.is_processable_element():
            return False

        process_kwargs: dict = {}
        if isinstance(self.options, dict):
            process_kwargs.update(**self.options)
        (changed, status) = await element.process(session, **process_kwargs)
        now = datetime.now()
        update_dict = {"time_updated": now}
        if status.is_successful_element():
            update_dict.update(time_finished=now)

        await self.update_values(session, **update_dict)
        await session.commit()
        return element.status.is_processable_element()

    async def process_element(
        self,
        session: async_scoped_session,
    ) -> bool:
        """Process associated element"""
        if self.waiting():
            return True
        return await self._process_and_update(session)

    async def process_element_loop(
        self,
        session: async_scoped_session,
    ) -> None:
        can_continue = True
        while can_continue:
            self.pause_until_next_check()
            can_continue = await self._process_and_update(session)
