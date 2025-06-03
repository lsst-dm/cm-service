from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import JSON, and_, select
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from ..common.enums import LevelEnum
from ..common.errors import CMBadEnumError, CMMissingFullnameError
from ..common.logging import LOGGER
from .base import Base
from .campaign import Campaign
from .group import Group
from .job import Job
from .node import NodeMixin
from .script import Script
from .step import Step

logger = LOGGER.bind(module=__name__)


class Queue(Base, NodeMixin):
    """Database table to implement processing queue"""

    __tablename__ = "queue"
    class_string = "queue"

    id: Mapped[int] = mapped_column(primary_key=True)
    time_created: Mapped[datetime] = mapped_column(type_=TIMESTAMP(timezone=True))
    time_updated: Mapped[datetime] = mapped_column(type_=TIMESTAMP(timezone=True))
    time_finished: Mapped[datetime | None] = mapped_column(type_=TIMESTAMP(timezone=True), default=None)
    time_next_check: Mapped[datetime | None] = mapped_column(
        type_=TIMESTAMP(timezone=True), default=datetime.min.replace(tzinfo=UTC)
    )
    interval: Mapped[float] = mapped_column(default=300.0)
    options: Mapped[dict | list | None] = mapped_column(type_=JSON)
    node_level: Mapped[LevelEnum] = mapped_column()
    node_id: Mapped[int] = mapped_column()

    c_id: Mapped[int | None] = mapped_column(ForeignKey("campaign.id", ondelete="CASCADE"), index=True)
    s_id: Mapped[int | None] = mapped_column(ForeignKey("step.id", ondelete="CASCADE"), index=True)
    g_id: Mapped[int | None] = mapped_column(ForeignKey("group.id", ondelete="CASCADE"), index=True)
    j_id: Mapped[int | None] = mapped_column(ForeignKey("job.id", ondelete="CASCADE"), index=True)
    script_id: Mapped[int | None] = mapped_column(ForeignKey("script.id", ondelete="CASCADE"), index=True)

    c_: Mapped[Campaign] = relationship("Campaign", viewonly=True)
    s_: Mapped[Step] = relationship("Step", viewonly=True)
    g_: Mapped[Group] = relationship("Group", viewonly=True)
    j_: Mapped[Job] = relationship("Job", viewonly=True)
    script_: Mapped[Job] = relationship("Script", viewonly=True)

    col_names_for_table = [
        "id",
        "node_id",
        "interval",
        "time_created",
        "time_updated",
        "time_finished",
        "time_next_check",
    ]

    async def get_node(
        self,
        session: async_scoped_session,
    ) -> NodeMixin:
        """Get the parent `Node`

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        node : NodeMixin
            Requested Parent Node
        """
        node: NodeMixin | None = None
        if self.node_level is LevelEnum.campaign:
            await session.refresh(self, attribute_names=["c_"])
            node = self.c_
        elif self.node_level is LevelEnum.step:
            await session.refresh(self, attribute_names=["s_"])
            node = self.s_
        elif self.node_level is LevelEnum.group:
            await session.refresh(self, attribute_names=["g_"])
            node = self.g_
        elif self.node_level is LevelEnum.job:
            await session.refresh(self, attribute_names=["j_"])
            node = self.j_
        elif self.node_level is LevelEnum.script:
            await session.refresh(self, attribute_names=["script_"])
            node = self.script_
        else:  # pragma: no cover
            raise CMBadEnumError(f"Bad level for script: {self.node_level}")
        return node

    @classmethod
    async def get_queue_item(
        cls,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> Queue:
        """Get the queue row corresponding to a partiuclar node

        Parameters
        ----------
        session : async_scoped_session
            DB session manager
        Keywords
        --------
        fullname: str
            Fullname of the associated elememnt
        Returns
        -------
        queue : Queue
            Requested Queue row
        """
        fullname = kwargs["fullname"]
        node_level = LevelEnum.get_level_from_fullname(fullname)
        node: NodeMixin | None = None
        if node_level is LevelEnum.campaign:
            node = await Campaign.get_row_by_fullname(session, fullname)
        elif node_level is LevelEnum.step:
            node = await Step.get_row_by_fullname(session, fullname)
        elif node_level is LevelEnum.group:
            node = await Group.get_row_by_fullname(session, fullname)
        elif node_level is LevelEnum.job:
            node = await Job.get_row_by_fullname(session, fullname)
        elif node_level is LevelEnum.script:
            # parse out the "script:" at the beginning fof ullname
            node = await Script.get_row_by_fullname(session, fullname[7:])
        else:  # pragma: no cover
            raise CMBadEnumError(f"Bad level for queue: {node_level}")
        query = select(cls).where(
            and_(
                cls.node_level == node_level,
                cls.node_id == node.id,
            ),
        )
        rows = await session.scalars(query)
        row = rows.first()
        if row is None:  # pragma: no cover
            raise CMMissingFullnameError(f"{cls} {node_level} {node.id} not found")
        return row

    @classmethod
    async def get_create_kwargs(
        cls,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> dict:
        fullname = kwargs["fullname"]
        node_level = LevelEnum.get_level_from_fullname(fullname)
        now = datetime.now(tz=UTC)
        ret_dict = {
            "node_level": node_level,
            "interval": kwargs.get("interval", 300),
            "time_created": now,
            "time_updated": now,
            "options": kwargs.get("options", {}),
        }

        node: NodeMixin | None = None
        if node_level is LevelEnum.campaign:
            node = await Campaign.get_row_by_fullname(session, fullname)
            ret_dict["c_id"] = node.id
        elif node_level is LevelEnum.step:
            node = await Step.get_row_by_fullname(session, fullname)
            ret_dict["s_id"] = node.id
        elif node_level is LevelEnum.group:
            node = await Group.get_row_by_fullname(session, fullname)
            ret_dict["g_id"] = node.id
        elif node_level is LevelEnum.job:
            node = await Job.get_row_by_fullname(session, fullname)
            ret_dict["j_id"] = node.id
        elif node_level is LevelEnum.script:
            # parse out the "script:" at the beginning fof ullname
            node = await Script.get_row_by_fullname(session, fullname[7:])
            ret_dict["script_id"] = node.id
        else:  # pragma: no cover
            raise CMBadEnumError(f"Bad level for queue: {node_level}")

        ret_dict["node_id"] = node.id
        return ret_dict

    async def node_sleep_time(
        self,
        session: async_scoped_session,
    ) -> int:
        """Check how long to sleep based on what is running"""
        node = await self.get_node(session)
        return await node.estimate_sleep_time(session)

    # TODO: who is asking? Not the daemon.
    def waiting(
        self,
    ) -> bool:
        """Check if this the Queue Node is done waiting

        Returns
        -------
        done: bool
            Returns True if still waiting
        """
        delta_t = timedelta(seconds=self.interval)
        next_check = self.time_updated + delta_t
        now = datetime.now(tz=UTC)
        return now < next_check

    async def process_node(
        self,
        session: async_scoped_session,
    ) -> bool:  # pragma: no cover
        """Process associated node and update queue row"""
        node = await self.get_node(session)

        if node.level is LevelEnum.script:
            logger.debug("Processing a %s", node.level)
            if not node.status.is_processable_script():
                return False
        if not node.status.is_processable_element():
            logger.debug("Node %s is not processable", node.name)
            return False

        process_kwargs: dict = {}
        if isinstance(self.options, dict):
            process_kwargs.update(**self.options)
        (_changed, status) = await node.process(session, **process_kwargs)

        now = datetime.now(tz=UTC)
        update_dict = {"time_updated": now}

        if node.level is LevelEnum.script:
            if status.is_successful_script():
                update_dict.update(time_finished=now)
        else:
            if status.is_successful_element():
                update_dict.update(time_finished=now)

        await self.update_values(session, **update_dict)
        if node.level is LevelEnum.script:
            node.status.is_processable_script()
        return node.status.is_processable_element()
