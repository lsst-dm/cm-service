from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from ..common.enums import LevelEnum, StatusEnum
from ..common.errors import CMMissingRowCreateInputError
from ..models.merged_product_set import MergedProductSetDict
from ..models.merged_task_set import MergedTaskSetDict
from ..models.merged_wms_task_report import MergedWmsTaskReportDict
from .base import Base
from .element import ElementMixin
from .spec_block import SpecBlock
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
    class_string = "campaign"

    id: Mapped[int] = mapped_column(primary_key=True)
    spec_id: Mapped[int] = mapped_column(
        ForeignKey("specification.id", ondelete="CASCADE"),
        index=True,
    )
    spec_block_id: Mapped[int] = mapped_column(
        ForeignKey("spec_block.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(index=True)
    fullname: Mapped[str] = mapped_column(unique=True)
    status: Mapped[StatusEnum] = mapped_column(default=StatusEnum.waiting)
    superseded: Mapped[bool] = mapped_column(default=False)
    handler: Mapped[str | None] = mapped_column()
    data: Mapped[dict | list | None] = mapped_column(type_=JSON)
    metadata_: Mapped[dict] = mapped_column("metadata_", type_=MutableDict.as_mutable(JSONB), default=dict)
    child_config: Mapped[dict | list | None] = mapped_column(type_=JSON)
    collections: Mapped[dict | list | None] = mapped_column(type_=JSON)
    spec_aliases: Mapped[dict | list | None] = mapped_column(type_=JSON)

    spec_: Mapped[Specification] = relationship(
        "Specification",
        primaryjoin="Specification.id==Campaign.spec_id",
        viewonly=True,
    )
    spec_block_: Mapped[SpecBlock] = relationship(
        "SpecBlock",
        primaryjoin="SpecBlock.id==Campaign.spec_block_id",
        viewonly=True,
    )

    s_: Mapped[list[Step]] = relationship("Step", viewonly=True)
    scripts_: Mapped[list[Script]] = relationship("Script", viewonly=True)
    jobs_: Mapped[list[Job]] = relationship(
        "Job",
        primaryjoin="Campaign.id==Step.parent_id",
        secondary="join(Step, Group).join(Job)",
        secondaryjoin="and_(Step.id==Group.parent_id, Job.parent_id==Group.id)",
        viewonly=True,
    )

    col_names_for_table = ["id", "fullname", "spec_id", "spec_block_id", "handler", "status", "superseded"]

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
        name = kwargs["name"]
        spec_block_assoc_name = kwargs.get("spec_block_assoc_name", None)
        if not spec_block_assoc_name:
            try:
                spec_name = kwargs["spec_name"]
                spec_block_name = kwargs.get("spec_block_name", "campaign")
            except KeyError as e:
                raise CMMissingRowCreateInputError(
                    "Spec_name required",
                ) from e
        else:
            tokens = spec_block_assoc_name.split("#")
            if len(tokens) != 2:
                raise ValueError(
                    f"spec_block_assoc_name not in format spec_name#campaign: {spec_block_assoc_name}",
                )
            spec_name = tokens[0]
            spec_block_name = tokens[1]

        specification = await Specification.get_row_by_fullname(
            session,
            spec_name,
        )

        data = kwargs.get("data", {})
        if data is None:
            data = {}
        child_config = kwargs.get("child_config", {})
        if child_config is None:
            child_config = {}
        collections = kwargs.get("collections", {})
        if collections is None:
            collections = {}
        spec_aliases = kwargs.get("spec_aliases", {})
        if spec_aliases is None:
            spec_aliases = {}

        await session.refresh(
            specification,
            attribute_names=["spec_aliases", "data", "child_config", "collections"],
        )
        if specification.data:
            assert isinstance(specification.data, dict)
            data.update(**specification.data)
        if specification.child_config:
            assert isinstance(specification.child_config, dict)
            child_config.update(**specification.child_config)
        if specification.collections:
            assert isinstance(specification.collections, dict)
            collections.update(**specification.collections)

        assert isinstance(specification.spec_aliases, dict)
        spec_aliases.update(**specification.spec_aliases)
        spec_block_resolved_name = spec_aliases[spec_block_name]

        spec_block = await SpecBlock.get_row_by_fullname(
            session,
            spec_block_resolved_name,
        )

        return {
            "spec_id": specification.id,
            "spec_block_id": spec_block.id,
            "name": name,
            "fullname": name,
            "handler": kwargs.get("handler"),
            "data": data,
            "child_config": child_config,
            "collections": collections,
            "spec_aliases": spec_aliases,
        }
