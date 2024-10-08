from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from ..common.enums import LevelEnum, NodeTypeEnum, ScriptMethodEnum, StatusEnum
from ..common.errors import CMBadEnumError, CMMissingRowCreateInputError
from .base import Base
from .campaign import Campaign
from .dbid import DbId
from .element import ElementMixin
from .enums import SqlLevelEnum, SqlScriptMethodEnum, SqlStatusEnum
from .group import Group
from .job import Job
from .node import NodeMixin
from .row import RowMixin
from .script_dependency import ScriptDependency
from .spec_block import SpecBlock
from .step import Step

if TYPE_CHECKING:
    from .script_error import ScriptError


class Script(Base, NodeMixin):
    """Database table to manage processing `Script`

    A script is anything that run asynchronously and processes campaign data

    Scripts can be associated to any level of the processing heirarchy
    """

    __tablename__ = "script"
    class_string = "script"

    id: Mapped[int] = mapped_column(primary_key=True)
    spec_block_id: Mapped[int] = mapped_column(
        ForeignKey("spec_block.id", ondelete="CASCADE"),
        index=True,
    )
    parent_level: Mapped[LevelEnum] = mapped_column(type_=SqlLevelEnum)
    parent_id: Mapped[int] = mapped_column()
    c_id: Mapped[int | None] = mapped_column(ForeignKey("campaign.id", ondelete="CASCADE"), index=True)
    s_id: Mapped[int | None] = mapped_column(ForeignKey("step.id", ondelete="CASCADE"), index=True)
    g_id: Mapped[int | None] = mapped_column(ForeignKey("group.id", ondelete="CASCADE"), index=True)
    j_id: Mapped[int | None] = mapped_column(ForeignKey("job.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(index=True)
    attempt: Mapped[int] = mapped_column(default=0)
    fullname: Mapped[str] = mapped_column(unique=True)
    status: Mapped[StatusEnum] = mapped_column(default=StatusEnum.waiting, type_=SqlStatusEnum)  # Status flag
    method: Mapped[ScriptMethodEnum] = mapped_column(
        default=ScriptMethodEnum.default,
        type_=SqlScriptMethodEnum,
    )
    superseded: Mapped[bool] = mapped_column(default=False)  # Has this been superseded
    handler: Mapped[str | None] = mapped_column()
    data: Mapped[dict | list | None] = mapped_column(type_=JSON)
    child_config: Mapped[dict | list | None] = mapped_column(type_=JSON)
    collections: Mapped[dict | list | None] = mapped_column(type_=JSON)
    script_url: Mapped[str | None] = mapped_column()
    stamp_url: Mapped[str | None] = mapped_column()
    log_url: Mapped[str | None] = mapped_column()

    spec_block_: Mapped[SpecBlock] = relationship("SpecBlock", viewonly=True)
    c_: Mapped[Campaign] = relationship("Campaign", viewonly=True)
    s_: Mapped[Step] = relationship("Step", viewonly=True)
    g_: Mapped[Group] = relationship("Group", viewonly=True)
    j_: Mapped[Job] = relationship("Job", viewonly=True)
    errors_: Mapped[list[ScriptError]] = relationship("ScriptError", viewonly=True)
    prereqs_: Mapped[list[ScriptDependency]] = relationship(
        "ScriptDependency",
        foreign_keys="ScriptDependency.depend_id",
        viewonly=True,
    )
    depends_: Mapped[list[ScriptDependency]] = relationship(
        "ScriptDependency",
        foreign_keys="ScriptDependency.prereq_id",
        viewonly=True,
    )

    col_names_for_table = [
        "id",
        "fullname",
        "spec_block_id",
        "handler",
        "method",
        "stamp_url",
        "script_url",
        "status",
        "superseded",
    ]

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
        """Returns LevelEnum.script"""
        return LevelEnum.script

    async def get_campaign(
        self,
        session: async_scoped_session,
    ) -> Campaign:
        """Maps self.get_parent().c_ to self.get_campaign() for consistency"""
        parent = await self.get_parent(session)
        return await parent.get_campaign(session)

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
        else:  # pragma: no cover
            raise CMBadEnumError(f"Bad level for script: {self.parent_level}")
        return element

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
            raise CMMissingRowCreateInputError(f"Missing input to create Script: {msg}") from msg
        attempt = kwargs.get("attempt", 0)
        parent_level = kwargs["parent_level"]

        ret_dict = {
            "parent_level": parent_level,
            "name": name,
            "attempt": attempt,
            "fullname": f"{parent_name}/{name}_{attempt:03}",
            "method": ScriptMethodEnum[kwargs.get("method", "default")],
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
        else:  # pragma: no cover
            raise CMBadEnumError(f"Bad level for script: {parent_level}")
        ret_dict["parent_id"] = element.id

        specification = await element.get_specification(session)
        spec_aliases = await element.get_spec_aliases(session)
        if spec_aliases:
            assert isinstance(spec_aliases, dict)
            spec_block_name = spec_aliases.get(spec_block_name, spec_block_name)
        spec_block = await specification.get_block(session, spec_block_name)
        ret_dict["spec_block_id"] = spec_block.id

        return ret_dict

    async def reset_script(
        self,
        session: async_scoped_session,
        to_status: StatusEnum,
    ) -> StatusEnum:
        """Reset a script to a lower status
        This will remove log files and processing
        files.

        This can not be used on script that have
        completed processing.

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        to_status : StatusEnum
            Status to set script to

        Returns
        -------
        status : StatusEnum
            New status
        """
        handler = await self.get_handler(session)
        return await handler.reset_script(session, self, to_status)
