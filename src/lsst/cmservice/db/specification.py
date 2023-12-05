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
    name: Mapped[str] = mapped_column(index=True)
    handler: Mapped[str | None] = mapped_column()
    data: Mapped[dict | list | None] = mapped_column(type_=JSON)
    collections: Mapped[dict | list | None] = mapped_column(type_=JSON)
    child_config: Mapped[dict | list | None] = mapped_column(type_=JSON)
    scripts: Mapped[dict | list | None] = mapped_column(type_=JSON)
    spec_aliases: Mapped[dict | list | None] = mapped_column(type_=JSON)

    col_names_for_table = ["id", "fullname", "handler"]

    @hybrid_property
    def fullname(self) -> str:
        """Maps name to fullname for consistency"""
        return self.name

    def __repr__(self) -> str:
        return f"SpecBlock {self.id}: {self.fullname} {self.data}"

    @classmethod
    async def get_create_kwargs(
        cls,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> dict:
        handler = kwargs["handler"]
        name = kwargs["name"]
        return {
            "name": name,
            "handler": handler,
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

    block_assocs_: Mapped[list[SpecBlockAssociation]] = relationship("SpecBlockAssociation", viewonly=True)
    script_template_assocs_: Mapped[list[ScriptTemplateAssociation]] = relationship(
        "ScriptTemplateAssociation",
        viewonly=True,
    )

    blocks_: Mapped[list[SpecBlock]] = relationship(
        "SpecBlock",
        primaryjoin="SpecBlockAssociation.spec_id==Specification.id",
        secondary="join(SpecBlockAssociation, SpecBlock)",
        secondaryjoin="SpecBlock.id==SpecBlockAssociation.spec_block_id",
        viewonly=True,
    )
    script_templates_: Mapped[list[ScriptTemplate]] = relationship(
        "ScriptTemplate",
        primaryjoin="ScriptTemplateAssociation.spec_id==Specification.id",
        secondary="join(ScriptTemplateAssociation, ScriptTemplate)",
        secondaryjoin="ScriptTemplate.id==ScriptTemplateAssociation.script_template_id",
        viewonly=True,
    )

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
            await session.refresh(self, attribute_names=["block_assocs_"])
            for block_assoc_ in self.block_assocs_:
                if block_assoc_.alias == spec_block_name:
                    await session.refresh(block_assoc_, attribute_names=["spec_block_"])
                    return block_assoc_.spec_block_
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
            await session.refresh(self, attribute_names=["script_template_assocs_"])
            for script_template_assoc_ in self.script_template_assocs_:
                if script_template_assoc_.alias == script_template_name:
                    await session.refresh(script_template_assoc_, attribute_names=["script_template_"])
                    return script_template_assoc_.script_template_
            raise KeyError(f"Could not find ScriptTemplate {script_template_name} in {self}")


class SpecBlockAssociation(Base, RowMixin):
    """Database table to manage connections between
    SpecBlocks and Specifications
    """

    __tablename__ = "spec_block_association"

    id: Mapped[int] = mapped_column(primary_key=True)
    spec_id: Mapped[int] = mapped_column(ForeignKey("specification.id", ondelete="CASCADE"), index=True)
    spec_block_id: Mapped[int] = mapped_column(ForeignKey("spec_block.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column()
    fullname: Mapped[str] = mapped_column(unique=True)

    spec_: Mapped[Specification] = relationship("Specification", viewonly=True)
    spec_block_: Mapped[SpecBlock] = relationship("SpecBlock", viewonly=True)

    col_names_for_table = ["id", "fullname", "alias"]

    @classmethod
    async def get_create_kwargs(
        cls,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> dict:
        spec_name = kwargs["spec_name"]
        spec_block_name = kwargs["spec_block_name"]
        alias = kwargs.get("alias", spec_block_name)
        spec = await Specification.get_row_by_fullname(session, spec_name)
        spec_block = await SpecBlock.get_row_by_fullname(session, spec_block_name)
        ret_dict = {
            "spec_id": spec.id,
            "spec_block_id": spec_block.id,
            "alias": alias,
            "fullname": f"{spec_name}#{spec_block_name}",
        }
        return ret_dict


class ScriptTemplateAssociation(Base, RowMixin):
    """Database table to manage connections between
    ScriptTemplatess and Specifications
    """

    __tablename__ = "script_template_association"

    id: Mapped[int] = mapped_column(primary_key=True)
    spec_id: Mapped[int] = mapped_column(ForeignKey("specification.id", ondelete="CASCADE"), index=True)
    script_template_id: Mapped[int] = mapped_column(
        ForeignKey("script_template.id", ondelete="CASCADE"),
        index=True,
    )
    alias: Mapped[str | None] = mapped_column()
    fullname: Mapped[str] = mapped_column(unique=True)

    spec_: Mapped[Specification] = relationship("Specification", viewonly=True)
    script_template_: Mapped[ScriptTemplate] = relationship("ScriptTemplate", viewonly=True)

    col_names_for_table = ["id", "fullname", "alias"]

    @classmethod
    async def get_create_kwargs(
        cls,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> dict:
        spec_name = kwargs["spec_name"]
        script_template_name = kwargs["script_template_name"]
        alias = kwargs.get("alias", script_template_name)
        spec = await Specification.get_row_by_fullname(session, spec_name)
        script_template = await ScriptTemplate.get_row_by_fullname(session, script_template_name)
        ret_dict = {
            "spec_id": spec.id,
            "script_template_id": script_template.id,
            "alias": alias,
            "fullname": f"{spec_name}#{script_template_name}",
        }
        return ret_dict
