from __future__ import annotations

from typing import Any

from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from .base import Base
from .row import RowMixin
from .script_template import ScriptTemplate


class SpecBlock(Base, RowMixin):
    """Database table to manage blocks that are used to build campaigns

    A 'SpecBlock' is tagged fragment of a yaml file that specifies how
    to build an element of a campaign
    """

    __tablename__ = "spec_block"

    id: Mapped[int] = mapped_column(primary_key=True)
    spec_id: Mapped[int] = mapped_column(ForeignKey("specification.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(index=True)
    fullname: Mapped[str] = mapped_column(unique=True)
    handler: Mapped[str | None] = mapped_column()
    data: Mapped[dict | list | None] = mapped_column(type_=JSON)
    collections: Mapped[dict | list | None] = mapped_column(type_=JSON)
    child_config: Mapped[dict | list | None] = mapped_column(type_=JSON)
    scripts: Mapped[dict | list | None] = mapped_column(type_=JSON)
    spec_aliases: Mapped[dict | list | None] = mapped_column(type_=JSON)

    spec_: Mapped[Specification] = relationship("Specification", viewonly=True)

    col_names_for_table = ["id", "fullname", "handler"]

    def __repr__(self) -> str:
        return f"SpecBlock {self.id}: {self.fullname} {self.data}"

    @classmethod
    async def get_create_kwargs(
        cls,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> dict:
        spec_name = kwargs["spec_name"]
        spec = await Specification.get_row_by_fullname(session, spec_name)
        handler = kwargs["handler"]
        name = kwargs["name"]
        return {
            "spec_id": spec.id,
            "name": name,
            "handler": handler,
            "fullname": f"{spec_name}#{name}",
            "data": kwargs.get("data", {}),
            "collections": kwargs.get("collections", {}),
            "child_config": kwargs.get("child_config", {}),
            "scripts": kwargs.get("scripts", {}),
            "spec_aliases": kwargs.get("spec_aliases", {}),
        }


class Specification(Base, RowMixin):
    __tablename__ = "specification"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(index=True)

    blocks_: Mapped[list[SpecBlock]] = relationship("SpecBlock", viewonly=True)
    script_templates_: Mapped[list[ScriptTemplate]] = relationship("ScriptTemplate", viewonly=True)

    col_names_for_table = ["id", "name"]

    @hybrid_property
    def fullname(self) -> str:
        """Maps name to fullname for consistency"""
        return self.name

    def __repr__(self) -> str:
        return f"Spec. {self.id}: {self.name}"

    async def get_block(
        self,
        session: async_scoped_session,
        spec_block_name: str,
    ) -> SpecBlock:
        """Get a SpecBlock associated to this Specification

        Parameters
        ----------
        session: async_scoped_session
            DB session manager

        spec_block_name: str
            Name of the SpecBlock to return

        Returns
        -------
        spec_block: SpecBlock
            Requested SpecBlock
        """
        async with session.begin_nested():
            await session.refresh(self, attribute_names=["blocks_"])
            for block_ in self.blocks_:
                if block_.name == spec_block_name:
                    return block_
            raise KeyError(f"Could not find spec_block {spec_block_name} in {self}")

    async def get_script_template(
        self,
        session: async_scoped_session,
        script_template_name: str,
    ) -> ScriptTemplate:
        """Get a ScriptTemplate associated to this Specification

        Parameters
        ----------
        session: async_scoped_session
            DB session manager

        script_template_name: str
            Name of the ScriptTemplate to return

        Returns
        -------
        script_template: ScriptTemplate
            Requested ScriptTemplate
        """
        async with session.begin_nested():
            await session.refresh(self, attribute_names=["script_templates_"])
            for script_template_ in self.script_templates_:
                if script_template_.name == script_template_name:
                    return script_template_
            raise KeyError(f"Could not find ScriptTemplate {script_template_name} in {self}")
