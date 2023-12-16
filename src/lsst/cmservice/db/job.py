from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, and_, select
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
from .spec_block import SpecBlock
from .spec_block_association import SpecBlockAssociation
from .specification import Specification
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
    class_string = "job"

    id: Mapped[int] = mapped_column(primary_key=True)
    spec_block_assoc_id: Mapped[int] = mapped_column(
        ForeignKey("spec_block_association.id", ondelete="CASCADE"),
        index=True,
    )
    parent_id: Mapped[int] = mapped_column(ForeignKey("group.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(index=True)
    attempt: Mapped[int] = mapped_column()
    fullname: Mapped[str] = mapped_column(unique=True)
    status: Mapped[StatusEnum] = mapped_column(default=StatusEnum.waiting, type_=SqlStatusEnum)
    superseded: Mapped[bool] = mapped_column(default=False)
    handler: Mapped[str | None] = mapped_column()
    data: Mapped[dict | list | None] = mapped_column(type_=JSON)
    child_config: Mapped[dict | list | None] = mapped_column(type_=JSON)
    collections: Mapped[dict | list | None] = mapped_column(type_=JSON)
    spec_aliases: Mapped[dict | list | None] = mapped_column(type_=JSON)
    wms_job_id: Mapped[str | None] = mapped_column()
    stamp_url: Mapped[str | None] = mapped_column()

    spec_block_assoc_: Mapped[SpecBlockAssociation] = relationship("SpecBlockAssociation", viewonly=True)
    spec_: Mapped[Specification] = relationship(
        "Specification",
        primaryjoin="SpecBlockAssociation.id==Job.spec_block_assoc_id",
        secondary="join(SpecBlockAssociation, Specification)",
        secondaryjoin="SpecBlockAssociation.spec_id==Specification.id",
        viewonly=True,
    )
    spec_block_: Mapped[SpecBlock] = relationship(
        "SpecBlock",
        primaryjoin="SpecBlockAssociation.id==Job.spec_block_assoc_id",
        secondary="join(SpecBlockAssociation, SpecBlock)",
        secondaryjoin="SpecBlockAssociation.spec_block_id==SpecBlock.id",
        viewonly=True,
    )
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

    col_names_for_table = [
        "id",
        "fullname",
        "spec_block_assoc_id",
        "handler",
        "wms_job_id",
        "stamp_url",
        "status",
        "superseded",
    ]

    @hybrid_property
    def db_id(self) -> DbId:
        """Returns DbId"""
        return DbId(LevelEnum.job, self.id)

    @property
    def level(self) -> LevelEnum:
        return LevelEnum.job

    async def get_siblings(
        self,
        session: async_scoped_session,
    ) -> Sequence[Job]:
        """Get the sibling Jobs

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        siblings : List['Job']
            Requested siblings
        """
        q = select(Job).where(
            and_(
                Job.parent_id == self.parent_id,
                Job.name == self.name,
                Job.id != self.id,
            ),
        )
        async with session.begin_nested():
            rows = await session.scalars(q)
            return rows.all()

    def __repr__(self) -> str:
        return f"Job {self.fullname} {self.id} {self.status.name}"

    @classmethod
    async def get_create_kwargs(
        cls,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> dict:
        parent_name = kwargs["parent_name"]
        name = kwargs["name"]
        attempt = kwargs.get("attempt", 0)
        parent = await Group.get_row_by_fullname(session, parent_name)
        spec_block_assoc_name = kwargs.get("spec_block_assoc_name", None)
        if not spec_block_assoc_name:
            try:
                spec_name = kwargs["spec_name"]
                spec_block_name = kwargs["spec_block_name"]
                spec_block_assoc_name = f"{spec_name}#{spec_block_name}"
            except KeyError as msg:
                raise KeyError(
                    "Either spec_block_assoc_name or (spec_name and spec_block_name) required",
                ) from msg
        spec_block_assoc = await SpecBlockAssociation.get_row_by_fullname(
            session,
            spec_block_assoc_name,
        )
        return {
            "spec_block_assoc_id": spec_block_assoc.id,
            "parent_id": parent.id,
            "name": name,
            "attempt": attempt,
            "fullname": f"{parent_name}/{name}_{attempt:03}",
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
        siblings = await self.get_siblings(session)
        skip_colls = []
        attempt = 2
        for sib_ in siblings:
            attempt += 1
            if sib_.status.rescuable and not sib_.superseded:
                sib_colls = await sib_.resolve_collections(session)
                skip_colls.append(sib_colls["job_run"])

        self_colls = await self.resolve_collections(session)
        skip_colls.append(self_colls["job_run"])
        parent = await self.get_parent(session)

        fullname = f"{parent.fullname}/{self.name}_{attempt:03}"
        if self.data:
            assert isinstance(self.data, dict)
            data = self.data.copy()
        else:
            data = {}
        data["rescue"] = True
        data["skip_colls"] = ",".join(skip_colls)
        new_job = Job(
            spec_block_assoc_id=self.spec_block_assoc_id,
            parent_id=self.parent_id,
            name=self.name,
            attempt=attempt,
            fullname=fullname,
            status=StatusEnum.waiting,
            superseded=False,
            handler=self.handler,
            data=data,
            child_config=self.child_config,
            collections=self.collections,
            spec_aliases=self.spec_aliases,
            wms_job_id=None,
            stamp_url=None,
        )
        async with session.begin_nested():
            session.add(new_job)
        await session.refresh(new_job)
        return new_job
