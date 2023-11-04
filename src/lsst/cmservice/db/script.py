from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional, Sequence

from sqlalchemy import JSON, and_, select
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from ..common.enums import LevelEnum, NodeTypeEnum, ScriptMethod, StatusEnum
from .base import Base
from .campaign import Campaign
from .dbid import DbId
from .element import ElementMixin
from .group import Group
from .job import Job
from .node import NodeMixin
from .row import RowMixin
from .specification import SpecBlock
from .step import Step

if TYPE_CHECKING:
    from .dependency import ScriptDependency
    from .script_error import ScriptError


class Script(Base, NodeMixin):
    """Database table to manage processing `Script`

    A script is anything that run asynchronously and processes campaign data

    Scripts can be associated to any level of the processing heirarchy
    """

    __tablename__ = "script"

    id: Mapped[int] = mapped_column(primary_key=True)
    spec_block_id: Mapped[int] = mapped_column(ForeignKey("spec_block.id", ondelete="CASCADE"), index=True)
    parent_level: Mapped[LevelEnum] = mapped_column()
    parent_id: Mapped[int] = mapped_column()
    c_id: Mapped[int | None] = mapped_column(ForeignKey("campaign.id", ondelete="CASCADE"), index=True)
    s_id: Mapped[int | None] = mapped_column(ForeignKey("step.id", ondelete="CASCADE"), index=True)
    g_id: Mapped[int | None] = mapped_column(ForeignKey("group.id", ondelete="CASCADE"), index=True)
    j_id: Mapped[int | None] = mapped_column(ForeignKey("job.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(index=True)
    attempt: Mapped[int] = mapped_column(default=0)
    fullname: Mapped[str] = mapped_column(unique=True)
    status: Mapped[StatusEnum] = mapped_column(default=StatusEnum.waiting)  # Status flag
    method: Mapped[ScriptMethod] = mapped_column(default=ScriptMethod.default)
    superseded: Mapped[bool] = mapped_column(default=False)  # Has this been supersede
    handler: Mapped[str | None] = mapped_column()
    data: Mapped[Optional[dict | list]] = mapped_column(type_=JSON)
    child_config: Mapped[Optional[dict | list]] = mapped_column(type_=JSON)
    collections: Mapped[Optional[dict | list]] = mapped_column(type_=JSON)
    script_url: Mapped[str | None] = mapped_column()
    stamp_url: Mapped[str | None] = mapped_column()
    log_url: Mapped[str | None] = mapped_column()

    spec_block_: Mapped["SpecBlock"] = relationship("SpecBlock", viewonly=True)
    c_: Mapped["Campaign"] = relationship("Campaign", viewonly=True)
    s_: Mapped["Step"] = relationship("Step", viewonly=True)
    g_: Mapped["Group"] = relationship("Group", viewonly=True)
    j_: Mapped["Job"] = relationship("Job", viewonly=True)
    errors_: Mapped[List["ScriptError"]] = relationship("ScriptError", viewonly=True)
    prereqs_: Mapped[List["ScriptDependency"]] = relationship(
        "ScriptDependency",
        foreign_keys="ScriptDependency.depend_id",
        viewonly=True,
    )

    @hybrid_property
    def db_id(self) -> DbId:
        """Returns DbId"""
        return DbId(LevelEnum.script, self.id)

    @hybrid_property
    def parent_db_id(self) -> DbId:
        """Returns DbId"""
        return DbId(self.parent_level, self.parent_id)

    @property
    def level(self) -> LevelEnum:
        return LevelEnum.script

    @property
    def node_type(self) -> NodeTypeEnum:
        """There are `Script` nodes"""
        return NodeTypeEnum.script

    async def get_parent(
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
            if self.parent_level == LevelEnum.campaign:
                await session.refresh(self, attribute_names=["c_"])
                element = self.c_
            elif self.parent_level == LevelEnum.step:
                await session.refresh(self, attribute_names=["s_"])
                element = self.s_
            elif self.parent_level == LevelEnum.group:
                await session.refresh(self, attribute_names=["g_"])
                element = self.g_
            elif self.parent_level == LevelEnum.job:
                await session.refresh(self, attribute_names=["j_"])
                element = self.j_
            else:
                raise ValueError(f"Bad level for script: {self.parent_level}")
            return element

    async def get_siblings(
        self,
        session: async_scoped_session,
    ) -> Sequence[Script]:
        """Get the sibling scripts

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        siblings : List['Script']
            Requested siblings
        """
        q = select(Script).where(
            and_(
                Script.parent_id == self.parent_id,
                Script.parent_level == self.parent_level,
                Script.name == self.name,
                Script.id != self.id,
            )
        )
        async with session.begin_nested():
            rows = await session.scalars(q)
            return rows.all()

    @classmethod
    async def get_create_kwargs(
        cls,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> dict:
        parent_name = kwargs["parent_name"]
        name = kwargs["name"]
        attempt = kwargs.get("attempt", 0)
        spec_block_name = kwargs["spec_block_name"]
        spec_block = await SpecBlock.get_row_by_fullname(session, spec_block_name)
        parent_level = kwargs["parent_level"]

        ret_dict = {
            "spec_block_id": spec_block.id,
            "parent_level": parent_level,
            "name": name,
            "attempt": attempt,
            "fullname": f"{parent_name}/{name}_{attempt:03}",
            "method": ScriptMethod[kwargs.get("method", "default")],
            "handler": kwargs.get("handler"),
            "data": kwargs.get("data", {}),
            "child_config": kwargs.get("child_config", {}),
            "collections": kwargs.get("collections", {}),
        }
        element: RowMixin | None = None
        if parent_level == LevelEnum.campaign:
            element = await Campaign.get_row_by_fullname(session, parent_name)
            ret_dict["c_id"] = element.id
        elif parent_level == LevelEnum.step:
            element = await Step.get_row_by_fullname(session, parent_name)
            ret_dict["s_id"] = element.id
        elif parent_level == LevelEnum.group:
            element = await Group.get_row_by_fullname(session, parent_name)
            ret_dict["g_id"] = element.id
        elif parent_level == LevelEnum.job:
            element = await Job.get_row_by_fullname(session, parent_name)
            ret_dict["j_id"] = element.id
        else:
            raise ValueError(f"Bad level for script: {parent_level}")
        ret_dict["parent_id"] = element.id
        return ret_dict

    async def copy_script(
        self,
        session: async_scoped_session,
    ) -> Script:
        """Copy a script `Script`

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        new_script: Script
            Newly created script
        """
        async with session.begin_nested():
            the_dict = self.__dict__
            sibs = await self.get_siblings(session)
            if sibs:
                the_dict["attempt"] = len(sibs) + 1
            else:
                the_dict["attempt"] = 1
            new_script = Script(**the_dict)
            session.add(new_script)
        await session.refresh(new_script)
        return new_script
