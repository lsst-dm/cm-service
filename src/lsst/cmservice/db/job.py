from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, and_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from ..common import timestamp
from ..common.enums import LevelEnum, StatusEnum
from ..common.errors import (
    CMIntegrityError,
    CMMissingRowCreateInputError,
    test_type_and_raise,
)
from ..models.merged_product_set import MergedProductSet, MergedProductSetDict
from ..models.merged_task_set import MergedTaskSet, MergedTaskSetDict
from ..models.merged_wms_task_report import MergedWmsTaskReport, MergedWmsTaskReportDict
from .base import Base
from .element import ElementMixin
from .group import Group
from .step import Step

if TYPE_CHECKING:
    from .campaign import Campaign
    from .pipetask_error import PipetaskError
    from .product_set import ProductSet
    from .script import Script
    from .spec_block import SpecBlock
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
    spec_block_id: Mapped[int] = mapped_column(
        ForeignKey("spec_block.id", ondelete="CASCADE"),
        index=True,
    )
    parent_id: Mapped[int] = mapped_column(ForeignKey("group.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(index=True)
    attempt: Mapped[int] = mapped_column()
    fullname: Mapped[str] = mapped_column(unique=True)
    status: Mapped[StatusEnum] = mapped_column(default=StatusEnum.waiting)
    superseded: Mapped[bool] = mapped_column(default=False)
    handler: Mapped[str | None] = mapped_column()
    data: Mapped[dict | list | None] = mapped_column(type_=JSON)
    metadata_: Mapped[dict] = mapped_column("metadata_", type_=MutableDict.as_mutable(JSONB), default=dict)
    child_config: Mapped[dict | list | None] = mapped_column(type_=JSON)
    collections: Mapped[dict | list | None] = mapped_column(type_=JSON)
    spec_aliases: Mapped[dict | list | None] = mapped_column(type_=JSON)
    wms_job_id: Mapped[str | None] = mapped_column()
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
        "spec_block_id",
        "handler",
        "wms_job_id",
        "stamp_url",
        "status",
        "superseded",
    ]

    @property
    def level(self) -> LevelEnum:
        """Returns LevelEnum.job"""
        return LevelEnum.job

    async def get_campaign(
        self,
        session: async_scoped_session,
    ) -> Campaign:
        """Maps self.c_ to self.get_campaign() for consistency"""
        await session.refresh(self, attribute_names=["c_"])
        return self.c_

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
        rows = await session.scalars(q)
        return rows.all()

    async def get_wms_reports(
        self,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> MergedWmsTaskReportDict:
        await session.refresh(self, attribute_names=["wms_reports_"])
        reports = {
            wms_report_.name: MergedWmsTaskReport.from_orm(wms_report_) for wms_report_ in self.wms_reports_
        }
        return MergedWmsTaskReportDict(reports=reports)

    async def get_tasks(
        self,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> MergedTaskSetDict:
        await session.refresh(self, attribute_names=["tasks_"])
        reports = {task_.name: MergedTaskSet.from_orm(task_) for task_ in self.tasks_}
        return MergedTaskSetDict(reports=reports)

    async def get_products(
        self,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> MergedProductSetDict:
        await session.refresh(self, attribute_names=["products_"])
        reports = {product_.name: MergedProductSet.from_orm(product_) for product_ in self.products_}
        return MergedProductSetDict(reports=reports)

    async def get_errors(
        self,
        session: async_scoped_session,
    ) -> Sequence[PipetaskError]:
        await session.refresh(self, attribute_names=["errors_"])
        return self.errors_

    def __repr__(self) -> str:
        return f"Job {self.fullname} {self.id} {self.status.name}"

    @classmethod
    async def get_create_kwargs(
        cls,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> dict:
        try:
            parent_name = kwargs["parent_name"]
            name = kwargs["name"]
            spec_block_name = kwargs["spec_block_name"]
        except KeyError as e:
            raise CMMissingRowCreateInputError(f"Missing input to create Job: {e}") from e
        attempt = kwargs.get("attempt", 0)
        parent = await Group.get_row_by_fullname(session, parent_name)
        spec_aliases = await parent.get_spec_aliases(session)
        spec_block_name = spec_aliases.get(spec_block_name, spec_block_name)
        specification = await parent.get_specification(session)
        spec_block = await specification.get_block(session, spec_block_name)

        metadata_ = kwargs.get("metadata", {})
        metadata_["crtime"] = timestamp.element_time()
        metadata_["mtime"] = None

        return {
            "spec_block_id": spec_block.id,
            "parent_id": parent.id,
            "name": name,
            "attempt": attempt,
            "fullname": f"{parent_name}/{name}_{attempt:03}",
            "handler": kwargs.get("handler"),
            "data": kwargs.get("data", {}),
            "metadata_": metadata_,
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
        attempt = 1
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
            data = test_type_and_raise(self.data, dict, "job.data").copy()
        else:  # pragma: no cover
            data = {}
        data["rescue"] = True
        data["skip_colls"] = ",".join(skip_colls)
        new_job = Job(
            spec_block_id=self.spec_block_id,
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
            try:
                session.add(new_job)
            except IntegrityError as msg:
                await session.rollback()
                if TYPE_CHECKING:
                    assert msg.orig  # for mypy
                raise CMIntegrityError(params=msg.params, orig=msg.orig, statement=msg.statement) from msg

        await session.refresh(new_job)
        return new_job

    async def get_jobs(
        self,
        session: async_scoped_session,
        *,
        remaining_only: bool = False,
        skip_superseded: bool = True,
    ) -> list[Job]:  # pragma: no cover
        return []
