from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey, UniqueConstraint

from ..common.enums import LevelEnum, StatusEnum
from .base import Base
from .campaign import Campaign
from .dbid import DbId
from .element import ElementMixin
from .enums import SqlStatusEnum
from .spec_block import SpecBlock
from .spec_block_association import SpecBlockAssociation
from .specification import Specification

if TYPE_CHECKING:
    from .group import Group
    from .job import Job
    from .production import Production
    from .script import Script
    from .step_dependency import StepDependency


class Step(Base, ElementMixin):
    """Database table to manage processing `Step`

    Several `Step` run in series comprise a `Campaign`

    A `Step` consists of several processing `Group` which
    are run in parallel.

    A `Step` is typically associated to a Pipeline subset
    """

    __tablename__ = "step"
    __table_args__ = (UniqueConstraint("parent_id", "name"),)  # Name must be unique within parent campaign

    id: Mapped[int] = mapped_column(primary_key=True)
    spec_block_assoc_id: Mapped[int] = mapped_column(
        ForeignKey("spec_block_association.id", ondelete="CASCADE"),
        index=True,
    )
    parent_id: Mapped[int] = mapped_column(ForeignKey("campaign.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(index=True)
    fullname: Mapped[str] = mapped_column(unique=True)
    status: Mapped[StatusEnum] = mapped_column(default=StatusEnum.waiting, type_=SqlStatusEnum)  # Status flag
    superseded: Mapped[bool] = mapped_column(default=False)  # Has this been supersede
    handler: Mapped[str | None] = mapped_column()
    data: Mapped[dict | list | None] = mapped_column(type_=JSON)
    child_config: Mapped[dict | list | None] = mapped_column(type_=JSON)
    collections: Mapped[dict | list | None] = mapped_column(type_=JSON)
    spec_aliases: Mapped[dict | list | None] = mapped_column(type_=JSON)

    spec_block_assoc_: Mapped[SpecBlockAssociation] = relationship("SpecBlockAssociation", viewonly=True)
    spec_: Mapped[Specification] = relationship(
        "Specification",
        primaryjoin="SpecBlockAssociation.id==Step.spec_block_assoc_id",
        secondary="join(SpecBlockAssociation, Specification)",
        secondaryjoin="SpecBlockAssociation.spec_id==Specification.id",
        viewonly=True,
    )
    spec_block_: Mapped[SpecBlock] = relationship(
        "SpecBlock",
        primaryjoin="SpecBlockAssociation.id==Step.spec_block_assoc_id",
        secondary="join(SpecBlockAssociation, SpecBlock)",
        secondaryjoin="SpecBlockAssociation.spec_block_id==SpecBlock.id",
        viewonly=True,
    )
    parent_: Mapped[Campaign] = relationship("Campaign", back_populates="s_")
    p_: Mapped[Production] = relationship(
        "Production",
        primaryjoin="Step.parent_id==Campaign.id",
        secondary="join(Campaign, Production)",
        secondaryjoin="Campaign.parent_id==Production.id",
        viewonly=True,
    )
    g_: Mapped[list[Group]] = relationship("Group", viewonly=True)
    scripts_: Mapped[list[Script]] = relationship("Script", viewonly=True)
    prereqs_: Mapped[list[StepDependency]] = relationship(
        "StepDependency",
        foreign_keys="StepDependency.depend_id",
        viewonly=True,
    )
    jobs_: Mapped[list[Job]] = relationship(
        "Job",
        primaryjoin="Group.parent_id==Step.id",
        secondary="join(Group, Job)",
        secondaryjoin="Job.parent_id==Group.id",
        viewonly=True,
    )

    col_names_for_table = ["id", "fullname", "spec_block_id_assoc", "handler", "status", "superseded"]

    @hybrid_property
    def db_id(self) -> DbId:
        """Returns DbId"""
        return DbId(LevelEnum.step, self.id)

    @property
    def level(self) -> LevelEnum:
        return LevelEnum.step

    def __repr__(self) -> str:
        return f"Production {self.fullname} {self.id} {self.status.name}"

    async def children(
        self,
        session: async_scoped_session,
    ) -> Iterable:
        """Maps self.g_ to self.children() for consistency"""
        async with session.begin_nested():
            await session.refresh(self, attribute_names=["g_"])
            return self.g_

    @classmethod
    async def get_create_kwargs(
        cls,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> dict:
        parent_name = kwargs["parent_name"]
        name = kwargs["name"]
        campaign = await Campaign.get_row_by_fullname(session, parent_name)
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
            "parent_id": campaign.id,
            "name": name,
            "fullname": f"{campaign.fullname}/{name}",
            "handler": kwargs.get("handler"),
            "data": kwargs.get("data", {}),
            "child_config": kwargs.get("child_config", {}),
            "collections": kwargs.get("collections", {}),
            "spec_aliases": kwargs.get("spec_aliases", {}),
        }
