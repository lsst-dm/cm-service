from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey, UniqueConstraint

from ..common import timestamp
from ..common.enums import LevelEnum, StatusEnum
from ..common.errors import (
    CMBadStateTransitionError,
    CMIntegrityError,
    CMMissingRowCreateInputError,
    CMTooFewAcceptedJobsError,
    CMTooManyActiveScriptsError,
)
from ..common.types import AnyAsyncSession
from ..models.merged_product_set import MergedProductSetDict
from ..models.merged_task_set import MergedTaskSetDict
from ..models.merged_wms_task_report import MergedWmsTaskReportDict
from .base import Base
from .element import ElementMixin
from .spec_block import SpecBlock
from .step import Step

if TYPE_CHECKING:
    from .campaign import Campaign
    from .job import Job
    from .script import Script


class Group(Base, ElementMixin):
    """Database table to manage processing `Group`

    Several `Group`s run in parallel comprise a `Step`

    Each `Group` would ideally use a single `Job` to
    process the data associate to the `Group` through
    the Pipeline subset associated to the `Step`
    """

    __tablename__ = "group"
    __table_args__ = (UniqueConstraint("parent_id", "name"),)  # Name must be unique within parent step
    class_string = "group"

    id: Mapped[int] = mapped_column(primary_key=True)
    spec_block_id: Mapped[int] = mapped_column(
        ForeignKey("spec_block.id", ondelete="CASCADE"),
        index=True,
    )
    parent_id: Mapped[int] = mapped_column(ForeignKey("step.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(index=True)
    fullname: Mapped[str] = mapped_column(unique=True)
    status: Mapped[StatusEnum] = mapped_column(default=StatusEnum.waiting)
    superseded: Mapped[bool] = mapped_column(default=False)  # Has this been supersede
    handler: Mapped[str | None] = mapped_column()
    data: Mapped[dict] = mapped_column(type_=JSON, default=dict)
    metadata_: Mapped[dict] = mapped_column("metadata_", type_=MutableDict.as_mutable(JSONB), default=dict)
    child_config: Mapped[dict | list | None] = mapped_column(type_=JSON)
    collections: Mapped[dict | list | None] = mapped_column(type_=JSON)
    spec_aliases: Mapped[dict | None] = mapped_column(type_=JSON)

    spec_block_: Mapped[SpecBlock] = relationship("SpecBlock", viewonly=True)
    c_: Mapped["Campaign"] = relationship(
        "Campaign",
        primaryjoin="Group.parent_id==Step.id",
        secondary="join(Step, Campaign)",
        secondaryjoin="Step.parent_id==Campaign.id",
        viewonly=True,
    )

    parent_: Mapped["Step"] = relationship("Step", viewonly=True)
    scripts_: Mapped[list["Script"]] = relationship("Script", viewonly=True)
    jobs_: Mapped[list["Job"]] = relationship("Job", viewonly=True)

    col_names_for_table = ["id", "fullname", "spec_block_id", "handler", "status", "superseded"]

    @property
    def level(self) -> LevelEnum:
        """Returns LevelEnum.group"""
        return LevelEnum.group

    async def get_campaign(
        self,
        session: AnyAsyncSession,
    ) -> "Campaign":
        """Maps self.c_ to self.get_campaign() for consistency"""
        await session.refresh(self, attribute_names=["c_"])
        return self.c_

    def __repr__(self) -> str:
        return f"Group {self.fullname} {self.id} {self.status.name}"

    async def children(
        self,
        session: AnyAsyncSession,
    ) -> Iterable:
        """Maps self.g_ to self.children() for consistency"""
        await session.refresh(self, attribute_names=["jobs_"])
        return self.jobs_

    async def get_wms_reports(
        self,
        session: AnyAsyncSession,
        **kwargs: Any,
    ) -> MergedWmsTaskReportDict:
        the_dict = MergedWmsTaskReportDict(reports={})

        await session.refresh(self, attribute_names=["jobs_"])
        for job_ in self.jobs_:
            the_dict += await job_.get_wms_reports(session)
        return the_dict

    async def get_tasks(
        self,
        session: AnyAsyncSession,
        **kwargs: Any,
    ) -> MergedTaskSetDict:
        the_dict = MergedTaskSetDict(reports={})
        await session.refresh(self, attribute_names=["jobs_"])
        for job_ in self.jobs_:
            the_dict.merge(await job_.get_tasks(session))
        return the_dict

    async def get_products(
        self,
        session: AnyAsyncSession,
        **kwargs: Any,
    ) -> MergedProductSetDict:
        the_dict = MergedProductSetDict(reports={})
        await session.refresh(self, attribute_names=["jobs_"])
        for job_ in self.jobs_:
            the_dict.merge(await job_.get_products(session))
        return the_dict

    @classmethod
    async def get_create_kwargs(
        cls,
        session: AnyAsyncSession,
        **kwargs: Any,
    ) -> dict:
        try:
            parent_name = kwargs["parent_name"]
            name = kwargs["name"]
            spec_block_name = kwargs["spec_block_name"]
        except KeyError as e:
            raise CMMissingRowCreateInputError(f"Missing input to create Group: {e}") from e
        step = await Step.get_row_by_fullname(session, parent_name)
        spec_aliases = await step.get_spec_aliases(session)
        spec_block_name = spec_aliases.get(spec_block_name, spec_block_name)
        specification = await step.get_specification(session)
        spec_block = await specification.get_block(session, spec_block_name)

        data = kwargs.get("data") or {}

        metadata_ = kwargs.get("metadata", {})
        metadata_["crtime"] = timestamp.element_time()
        metadata_["mtime"] = None

        return {
            "spec_block_id": spec_block.id,
            "parent_id": step.id,
            "name": name,
            "fullname": f"{parent_name}/{name}",
            "handler": kwargs.get("handler"),
            "data": data,
            "metadata_": metadata_,
            "child_config": kwargs.get("child_config", {}),
            "collections": kwargs.get("collections", {}),
            "spec_aliases": kwargs.get("spec_aliases", {}),
        }

    async def rescue_job(
        self,
        session: AnyAsyncSession,
    ) -> "Job":
        """Create a rescue `Job`

        This will make a new `Job` in the DB

        Parameters
        ----------
        session : AnyAsyncSession
            DB session manager

        Returns
        -------
        job: Job
            Newly created Job
        """
        jobs = await self.get_jobs(session)
        rescuable_jobs = [j for j in jobs if j.status is StatusEnum.rescuable]
        if not rescuable_jobs:
            raise CMTooFewAcceptedJobsError(f"Expected at least one rescuable job for {self.fullname}, got 0")
        latest_resuable_job = rescuable_jobs[-1]
        try:
            new_job = await latest_resuable_job.copy_job(session, self)
            await session.commit()
        except IntegrityError as msg:
            if TYPE_CHECKING:
                assert msg.orig  # for mypy
            await session.rollback()
            raise CMIntegrityError(params=msg.params, orig=msg.orig, statement=msg.statement) from msg
        return new_job

    async def mark_job_rescued(
        self,
        session: AnyAsyncSession,
    ) -> list["Job"]:
        """Mark jobs as `rescued` once one of their siblings is `accepted`

        Parameters
        ----------
        session : AnyAsyncSession
            DB session manager

        Returns
        -------
        jobs: List[Job]
            Jobs marked as `rescued`
        """
        jobs = await self.get_jobs(session)
        has_accepted = False
        ret_list = []
        for job_ in jobs:
            if job_.status is StatusEnum.rescuable:
                ret_list.append(job_)
            elif job_.status is StatusEnum.rescued:
                pass
            elif job_.status is StatusEnum.accepted:
                if has_accepted:
                    raise CMTooManyActiveScriptsError(f"More that one accepted job found: {job_.fullname}")
                has_accepted = True
            else:
                raise CMBadStateTransitionError(
                    f"Job should be rescuable or accepted: {job_.fullname} is {job_.status}",
                )
        if not has_accepted:
            raise CMTooFewAcceptedJobsError(f"Expected at least one accepted job for {self.fullname}, got 0")
        for job_ in ret_list:
            await job_.update_values(session, status=StatusEnum.rescued)
        return ret_list
