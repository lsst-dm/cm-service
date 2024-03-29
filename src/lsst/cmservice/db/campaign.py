from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey, UniqueConstraint

from ..common.enums import LevelEnum, StatusEnum
from ..common.errors import CMMissingRowCreateInputError
from ..models.merged_product_set import MergedProductSetDict
from ..models.merged_task_set import MergedTaskSetDict
from ..models.merged_wms_task_report import MergedWmsTaskReportDict
from .base import Base
from .dbid import DbId
from .element import ElementMixin
from .enums import SqlStatusEnum
from .production import Production
from .spec_block import SpecBlock
from .spec_block_association import SpecBlockAssociation
from .specification import Specification

if TYPE_CHECKING:
    from .job import Job
    from .script import Script
    from .step import Step


class Campaign(Base, ElementMixin):
    """Database table to manage a processing `Campaign`

    A `Campaign` consists of several processing `Step` which
    are run sequentially.  Each `Step` is associated with
    a Pipeline subset.  The `Campaign` could be the any
    set of `Step`s, up to and beyond the entire Pipeline.
    (I.e., a `Campaign` may take `Step`s associated to
    multiple Pipeline yaml files.

    `Campaign` is also where we keep the global configuration
    such as the URL for the butler repo and the production area
    """

    __tablename__ = "campaign"
    __table_args__ = (UniqueConstraint("parent_id", "name"),)  # Name must be unique within parent production
    class_string = "campaign"

    id: Mapped[int] = mapped_column(primary_key=True)
    spec_block_assoc_id: Mapped[int] = mapped_column(
        ForeignKey("spec_block_association.id", ondelete="CASCADE"),
        index=True,
    )
    parent_id: Mapped[int] = mapped_column(ForeignKey("production.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(index=True)
    fullname: Mapped[str] = mapped_column(unique=True)
    status: Mapped[StatusEnum] = mapped_column(default=StatusEnum.waiting, type_=SqlStatusEnum)
    superseded: Mapped[bool] = mapped_column(default=False)
    handler: Mapped[str | None] = mapped_column()
    data: Mapped[dict | list | None] = mapped_column(type_=JSON)
    child_config: Mapped[dict | list | None] = mapped_column(type_=JSON)
    collections: Mapped[dict | list | None] = mapped_column(type_=JSON)
    spec_aliases: Mapped[dict | list | None] = mapped_column(type_=JSON)

    spec_block_assoc_: Mapped[SpecBlockAssociation] = relationship("SpecBlockAssociation", viewonly=True)
    spec_: Mapped[Specification] = relationship(
        "Specification",
        primaryjoin="SpecBlockAssociation.id==Campaign.spec_block_assoc_id",
        secondary="join(SpecBlockAssociation, Specification)",
        secondaryjoin="SpecBlockAssociation.spec_id==Specification.id",
        viewonly=True,
    )
    spec_block_: Mapped[SpecBlock] = relationship(
        "SpecBlock",
        primaryjoin="SpecBlockAssociation.id==Campaign.spec_block_assoc_id",
        secondary="join(SpecBlockAssociation, SpecBlock)",
        secondaryjoin="SpecBlockAssociation.spec_block_id==SpecBlock.id",
        viewonly=True,
    )

    parent_: Mapped[Production] = relationship("Production", viewonly=True)
    s_: Mapped[list[Step]] = relationship("Step", viewonly=True)
    scripts_: Mapped[list[Script]] = relationship("Script", viewonly=True)
    jobs_: Mapped[list[Job]] = relationship(
        "Job",
        primaryjoin="Campaign.id==Step.parent_id",
        secondary="join(Step, Group).join(Job)",
        secondaryjoin="and_(Step.id==Group.parent_id, Job.parent_id==Group.id)",
        viewonly=True,
    )

    col_names_for_table = ["id", "fullname", "spec_block_assoc_id", "handler", "status", "superseded"]

    @hybrid_property
    def db_id(self) -> DbId:
        """Returns DbId"""
        return DbId(LevelEnum.campaign, self.id)

    @property
    def level(self) -> LevelEnum:
        """Returns LevelEnum.campaign"""
        return LevelEnum.campaign

    async def get_campaign(
        self,
        session: async_scoped_session,
    ) -> Campaign:
        """Maps self to self.get_campaign() for consistency"""
        assert session  # For mypy
        return self

    def __repr__(self) -> str:
        return f"Campaign {self.fullname} {self.id} {self.status.name}"

    async def children(
        self,
        session: async_scoped_session,
    ) -> Iterable:
        """Maps self.s_ to self.children() for consistency"""
        await session.refresh(self, attribute_names=["s_"])
        return self.s_

    async def get_wms_reports(
        self,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> MergedWmsTaskReportDict:
        the_dict = MergedWmsTaskReportDict(reports={})

        await session.refresh(self, attribute_names=["s_"])
        for step_ in self.s_:
            the_dict += await step_.get_wms_reports(session)
        return the_dict

    async def get_tasks(
        self,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> MergedTaskSetDict:
        the_dict = MergedTaskSetDict(reports={})
        await session.refresh(self, attribute_names=["s_"])
        for step_ in self.s_:
            the_dict += await step_.get_tasks(session)
        return the_dict

    async def get_products(
        self,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> MergedProductSetDict:
        the_dict = MergedProductSetDict(reports={})
        await session.refresh(self, attribute_names=["s_"])
        for step_ in self.s_:
            the_dict += await step_.get_products(session)
        return the_dict

    @classmethod
    async def get_create_kwargs(
        cls,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> dict:
        parent_name = kwargs["parent_name"]
        name = kwargs["name"]
        production = await Production.get_row_by_fullname(session, parent_name)
        spec_block_assoc_name = kwargs.get("spec_block_assoc_name", None)
        if not spec_block_assoc_name:
            try:
                spec_name = kwargs["spec_name"]
                spec_block_name = kwargs["spec_block_name"]
                spec_block_assoc_name = f"{spec_name}#{spec_block_name}"
            except KeyError as msg:
                raise CMMissingRowCreateInputError(
                    "Either spec_block_assoc_name or (spec_name and spec_block_name) required",
                ) from msg
        spec_block_assoc = await SpecBlockAssociation.get_row_by_fullname(
            session,
            spec_block_assoc_name,
        )
        return {
            "spec_block_assoc_id": spec_block_assoc.id,
            "parent_id": production.id,
            "name": name,
            "fullname": f"{production.fullname}/{name}",
            "handler": kwargs.get("handler"),
            "data": kwargs.get("data", {}),
            "child_config": kwargs.get("child_config", {}),
            "collections": kwargs.get("collections", {}),
            "spec_aliases": kwargs.get("spec_aliases", {}),
        }
