from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey, UniqueConstraint

from ..common.enums import LevelEnum, StatusEnum
from ..common.errors import (
    CMBadStateTransitionError,
    CMMissingRowCreateInputError,
    CMTooFewAcceptedJobsError,
    CMTooManyActiveScriptsError,
)
from .base import Base
from .dbid import DbId
from .element import ElementMixin
from .enums import SqlStatusEnum
from .spec_block import SpecBlock
from .step import Step

if TYPE_CHECKING:
    from .campaign import Campaign
    from .job import Job
    from .production import Production
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
    status: Mapped[StatusEnum] = mapped_column(default=StatusEnum.waiting, type_=SqlStatusEnum)  # Status flag
    superseded: Mapped[bool] = mapped_column(default=False)  # Has this been supersede
    handler: Mapped[str | None] = mapped_column()
    data: Mapped[dict | list | None] = mapped_column(type_=JSON)
    child_config: Mapped[dict | list | None] = mapped_column(type_=JSON)
    collections: Mapped[dict | list | None] = mapped_column(type_=JSON)
    spec_aliases: Mapped[dict | list | None] = mapped_column(type_=JSON)

    spec_block_: Mapped[SpecBlock] = relationship("SpecBlock", viewonly=True)
    c_: Mapped["Campaign"] = relationship(
        "Campaign",
        primaryjoin="Group.parent_id==Step.id",
        secondary="join(Step, Campaign)",
        secondaryjoin="Step.parent_id==Campaign.id",
        viewonly=True,
    )
    p_: Mapped["Production"] = relationship(
        "Production",
        primaryjoin="Group.parent_id==Step.id",
        secondary="join(Step, Campaign).join(Production)",
        secondaryjoin="and_(Step.parent_id==Campaign.id, Campaign.parent_id==Production.id)",
        viewonly=True,
    )

    parent_: Mapped["Step"] = relationship("Step", viewonly=True)
    scripts_: Mapped[list["Script"]] = relationship("Script", viewonly=True)
    jobs_: Mapped[list["Job"]] = relationship("Job", viewonly=True)

    col_names_for_table = ["id", "fullname", "spec_block_id", "handler", "status", "superseded"]

    @hybrid_property
    def db_id(self) -> DbId:
        """Returns DbId"""
        return DbId(LevelEnum.group, self.id)

    @property
    def level(self) -> LevelEnum:
        return LevelEnum.group

    async def get_campaign(
        self,
        session: async_scoped_session,
    ) -> "Campaign":
        """Maps self.c_ to self.get_campaign() for consistency"""
        async with session.begin_nested():
            await session.refresh(self, attribute_names=["c_"])
            return self.c_

    def __repr__(self) -> str:
        return f"Group {self.fullname} {self.id} {self.status.name}"

    async def children(
        self,
        session: async_scoped_session,  # pylint: disable=unused-argument
    ) -> Iterable:
        """Maps self.g_ to self.children() for consistency"""
        async with session.begin_nested():
            await session.refresh(self, attribute_names=["jobs_"])
            return self.jobs_

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
        except KeyError as msg:
            raise CMMissingRowCreateInputError(f"Missing input to create Group: {msg}")
        step = await Step.get_row_by_fullname(session, parent_name)
        specification = await step.get_specification(session)
        spec_block = await specification.get_block(session, spec_block_name)
        return {
            "spec_block_id": spec_block.id,
            "parent_id": step.id,
            "name": name,
            "fullname": f"{parent_name}/{name}",
            "handler": kwargs.get("handler"),
            "data": kwargs.get("data", {}),
            "child_config": kwargs.get("child_config", {}),
            "collections": kwargs.get("collections", {}),
            "spec_aliases": kwargs.get("spec_aliases", {}),
        }

    async def rescue_job(
        self,
        session: async_scoped_session,
    ) -> "Job":
        """Create a rescue `Job`

        This will make a new `Job` in the DB

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        job: Job
            Newly created Job
        """
        jobs = await self.get_jobs(session)
        rescuable_jobs = []
        for job_ in jobs:
            if job_.status == StatusEnum.rescuable:
                rescuable_jobs.append(job_)
            else:
                raise CMBadStateTransitionError(f"Found unrescuable job: {job_.fullname}")
        if not rescuable_jobs:
            raise CMTooFewAcceptedJobsError(f"Expected at least one rescuable job for {self.fullname}, got 0")
        latest_resuable_job = rescuable_jobs[-1]
        new_job = await latest_resuable_job.copy_job(session, self)
        await session.commit()
        return new_job

    async def mark_job_rescued(
        self,
        session: async_scoped_session,
    ) -> list["Job"]:
        """Mark jobs as `rescued` once one of their siblings is `accepted`

        Parameters
        ----------
        session : async_scoped_session
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
            if job_.status == StatusEnum.rescuable:
                await job_.update_values(session, status=StatusEnum.rescued)
                ret_list.append(job_)
            elif job_.status != StatusEnum.accepted:
                raise CMBadStateTransitionError(
                    f"Job should be rescuable or accepted: {job_.fullname} is {job_.status}",
                )
            else:
                if has_accepted:
                    raise CMTooManyActiveScriptsError(f"More that one accepted job found: {job_.fullname}")
                has_accepted = True
        if not has_accepted:
            raise CMTooFewAcceptedJobsError(f"Expected at least one accepted job for {self.fullname}, got 0")
        await session.commit()
        return ret_list
