from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from ..common.enums import LevelEnum, StatusEnum
from .base import Base
from .dbid import DbId
from .element import ElementMixin
from .enums import SqlStatusEnum
from .group import Group
from .specification import SpecBlock
from .step import Step

if TYPE_CHECKING:
    from .campaign import Campaign
    from .pipetask_error import PipetaskError
    from .product_set import ProductSet
    from .production import Production
    from .script import Script
    from .task_set import TaskSet
    from .wms_task_report import WmsTaskReport


class Job(Base, ElementMixin):
    """Database table to manage processing `Job`

    A `Job` is a single high-throughput computing
    workflow.

    A `Job` can be the original run of the workflow
    or a `rescue` workflow used to complete the
    original workflow
    """

    __tablename__ = "job"

    id: Mapped[int] = mapped_column(primary_key=True)
    spec_block_id: Mapped[int] = mapped_column(ForeignKey("spec_block.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("group.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(index=True)
    fullname: Mapped[str] = mapped_column(unique=True)
    status: Mapped[StatusEnum] = mapped_column(default=StatusEnum.waiting, type_=SqlStatusEnum)
    superseded: Mapped[bool] = mapped_column(default=False)
    handler: Mapped[str | None] = mapped_column()
    data: Mapped[dict | list | None] = mapped_column(type_=JSON)
    child_config: Mapped[dict | list | None] = mapped_column(type_=JSON)
    collections: Mapped[dict | list | None] = mapped_column(type_=JSON)
    spec_aliases: Mapped[dict | list | None] = mapped_column(type_=JSON)
    wms_job_id: Mapped[int | None] = mapped_column()
    stamp_url: Mapped[str | None] = mapped_column()

    spec_block_: Mapped[SpecBlock] = relationship("SpecBlock", viewonly=True)
    s_: Mapped[Step] = relationship(
        "Step",
        primaryjoin="Job.parent_id==Group.id",
        secondary="join(Group, Step)",
        secondaryjoin="Group.parent_id==Step.id",
        viewonly=True,
    )
    c_: Mapped[Campaign] = relationship(
        "Campaign",
        primaryjoin="Job.parent_id==Group.id",
        secondary="join(Group, Step).join(Campaign)",
        secondaryjoin="and_(Group.parent_id==Step.id, Step.parent_id==Campaign.id) ",
        viewonly=True,
    )
    p_: Mapped[Production] = relationship(
        "Production",
        primaryjoin="Job.parent_id==Group.id",
        secondary="join(Group, Step).join(Campaign).join(Production)",
        secondaryjoin="and_("
        "Group.parent_id==Step.id, "
        "Step.parent_id==Campaign.id, "
        "Campaign.parent_id==Production.id, "
        ") ",
        viewonly=True,
    )
    parent_: Mapped[Group] = relationship("Group", viewonly=True)
    scripts_: Mapped[list[Script]] = relationship("Script", viewonly=True)
    tasks_: Mapped[list[TaskSet]] = relationship("TaskSet", viewonly=True)
    products_: Mapped[list[ProductSet]] = relationship("ProductSet", viewonly=True)
    errors_: Mapped[list[PipetaskError]] = relationship(
        "PipetaskError",
        primaryjoin="Job.id==TaskSet.job_id",
        secondary="join(TaskSet, PipetaskError)",
        secondaryjoin="PipetaskError.task_id==TaskSet.id",
        viewonly=True,
    )
    wms_reports_: Mapped[list[WmsTaskReport]] = relationship("WmsTaskReport", viewonly=True)

    @hybrid_property
    def db_id(self) -> DbId:
        """Returns DbId"""
        return DbId(LevelEnum.job, self.id)

    @property
    def level(self) -> LevelEnum:
        return LevelEnum.job

    @classmethod
    async def get_create_kwargs(
        cls,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> dict:
        parent_name = kwargs["parent_name"]
        name = kwargs["name"]
        spec_block_name = kwargs["spec_block_name"]
        spec_block = await SpecBlock.get_row_by_fullname(session, spec_block_name)
        parent = await Group.get_row_by_fullname(session, parent_name)

        return {
            "spec_block_id": spec_block.id,
            "parent_id": parent.id,
            "name": name,
            "fullname": f"{parent_name}/{name}",
            "handler": kwargs.get("handler"),
            "data": kwargs.get("data", {}),
            "child_config": kwargs.get("child_config", {}),
            "collections": kwargs.get("collections", {}),
            "spec_aliases": kwargs.get("spec_aliases", {}),
        }

    async def copy_job(
        self,
        session: async_scoped_session,
        parent: ElementMixin,
    ) -> Job:
        """Copy a Job

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        parent : ElementMixin
            Who the job is being copied for

        Returns
        -------
        new_job: Job
            Newly created Job
        """
        raise NotImplementedError
