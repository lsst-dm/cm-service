from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from ..common import timestamp
from ..common.enums import LevelEnum, NodeTypeEnum, ScriptMethodEnum, StatusEnum
from ..common.errors import CMBadEnumError, CMMissingRowCreateInputError
from ..config import config
from .base import Base
from .campaign import Campaign
from .element import ElementMixin
from .group import Group
from .job import Job
from .node import NodeMixin
from .row import RowMixin
from .script_dependency import ScriptDependency
from .spec_block import SpecBlock
from .step import Step

if TYPE_CHECKING:
    from ..common.types import AnyAsyncSession
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
    parent_level: Mapped[LevelEnum] = mapped_column()
    parent_id: Mapped[int] = mapped_column()
    c_id: Mapped[int | None] = mapped_column(ForeignKey("campaign.id", ondelete="CASCADE"), index=True)
    s_id: Mapped[int | None] = mapped_column(ForeignKey("step.id", ondelete="CASCADE"), index=True)
    g_id: Mapped[int | None] = mapped_column(ForeignKey("group.id", ondelete="CASCADE"), index=True)
    j_id: Mapped[int | None] = mapped_column(ForeignKey("job.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(index=True)
    attempt: Mapped[int] = mapped_column(default=0)
    fullname: Mapped[str] = mapped_column(unique=True)
    status: Mapped[StatusEnum] = mapped_column(default=StatusEnum.waiting)
    method: Mapped[ScriptMethodEnum] = mapped_column(default=ScriptMethodEnum.default)
    superseded: Mapped[bool] = mapped_column(default=False)  # Has this been superseded
    handler: Mapped[str | None] = mapped_column()
    data: Mapped[dict] = mapped_column(type_=JSON, default=dict)
    metadata_: Mapped[dict] = mapped_column("metadata_", type_=MutableDict.as_mutable(JSONB), default=dict)
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

    @property
    def run_method(self) -> ScriptMethodEnum:
        """Get a ``ScriptMethodEnum`` for the script, resolving the default
        method as necessary.
        """
        if self.method is ScriptMethodEnum.default:
            return config.script_handler
        else:
            return self.method

    @property
    def level(self) -> LevelEnum:
        """Returns LevelEnum.script"""
        return LevelEnum.script

    async def get_script_errors(
        self,
        session: AnyAsyncSession,
    ) -> list[ScriptError]:
        await session.refresh(self, attribute_names=["errors_"])
        return self.errors_

    async def get_campaign(
        self,
        session: AnyAsyncSession,
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
        session: AnyAsyncSession,
    ) -> ElementMixin:
        """Get the parent `Element`

        Parameters
        ----------
        session : AnyAsyncSession
            DB session manager

        Returns
        -------
        element : ElementMixin
            Requested Parent Element
        """
        element: ElementMixin | None = None
        if self.parent_level is LevelEnum.campaign:
            await session.refresh(self, attribute_names=["c_"])
            element = self.c_
        elif self.parent_level is LevelEnum.step:
            await session.refresh(self, attribute_names=["s_"])
            element = self.s_
        elif self.parent_level is LevelEnum.group:
            await session.refresh(self, attribute_names=["g_"])
            element = self.g_
        elif self.parent_level is LevelEnum.job:
            await session.refresh(self, attribute_names=["j_"])
            element = self.j_
        else:  # pragma: no cover
            msg = f"Bad level for script: {self.parent_level}"
            raise CMBadEnumError(msg)
        return element

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
            original_name = kwargs.get("original_name", name)
        except KeyError as e:
            msg = f"Missing input to create Script: {e}"
            raise CMMissingRowCreateInputError(msg) from e
        attempt = kwargs.get("attempt", 0)
        parent_level = kwargs.get("parent_level", None)
        if parent_level is None:
            parent_level = LevelEnum.get_level_from_fullname(parent_name)
        if isinstance(parent_level, int):
            parent_level = LevelEnum(parent_level)

        data = kwargs.get("data") or {}

        metadata_ = kwargs.get("metadata", {})
        metadata_["crtime"] = timestamp.element_time()
        metadata_["mtime"] = None

        # The fullname should reflect the element's original shortname not its
        # namespaced name
        ret_dict = {
            "parent_level": parent_level,
            "name": name,
            "attempt": attempt,
            "fullname": f"{parent_name}/{original_name}_{attempt:03}",
            "method": ScriptMethodEnum[kwargs.get("method", "default")],
            "handler": kwargs.get("handler"),
            "data": data,
            "metadata_": metadata_,
            "child_config": kwargs.get("child_config", {}),
            "collections": kwargs.get("collections", {}),
        }
        element: RowMixin | None = None
        if parent_level is LevelEnum.campaign:
            element = await Campaign.get_row_by_fullname(session, parent_name)
            ret_dict["c_id"] = element.id
        elif parent_level is LevelEnum.step:
            element = await Step.get_row_by_fullname(session, parent_name)
            ret_dict["s_id"] = element.id
        elif parent_level is LevelEnum.group:
            element = await Group.get_row_by_fullname(session, parent_name)
            ret_dict["g_id"] = element.id
        elif parent_level is LevelEnum.job:
            element = await Job.get_row_by_fullname(session, parent_name)
            ret_dict["j_id"] = element.id
        else:  # pragma: no cover
            msg = f"Bad level for script: {parent_level}"
            raise CMBadEnumError(msg)
        ret_dict["parent_id"] = element.id

        specification = await element.get_specification(session)
        spec_aliases = await element.get_spec_aliases(session)
        spec_block_name = spec_aliases.get(spec_block_name, spec_block_name)
        spec_block = await specification.get_block(session, spec_block_name)
        ret_dict["spec_block_id"] = spec_block.id

        return ret_dict

    async def reset_script(
        self,
        session: AnyAsyncSession,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> StatusEnum:
        """Reset a script to a lower status
        This will remove log files and processing
        files.

        This can not be used on script that have
        completed processing.

        Parameters
        ----------
        session : AnyAsyncSession
            DB session manager

        to_status : StatusEnum
            Status to set script to

        fake_reset: bool
            Don't actually try to remove collections if True

        Returns
        -------
        status : StatusEnum
            New status
        """
        handler = await self.get_handler(session)
        return await handler.reset_script(session, self, to_status, fake_reset=fake_reset)

    async def review(
        self,
        session: AnyAsyncSession,
        **kwargs: Any,
    ) -> StatusEnum:
        """Run review() function on this Script

        This will create a `Handler` and
        pass this node to it for review

        Parameters
        ----------
        session : AnyAsyncSession
            DB session manager

        Returns
        -------
        status : StatusEnum
            Status of the processing
        """
        handler = await self.get_handler(session)
        parent = await self.get_parent(session)
        return await handler.review_script(session, self, parent, **kwargs)
