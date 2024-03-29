from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..common.errors import CMSpecficiationError
from .base import Base
from .row import RowMixin
from .script_template import ScriptTemplate
from .spec_block import SpecBlock

if TYPE_CHECKING:
    from .script_template_association import ScriptTemplateAssociation
    from .spec_block_association import SpecBlockAssociation


class Specification(Base, RowMixin):
    """Database table to manage mapping and grouping of SpecBlock
    and ScriptTemplate by associating them to a Specification

    The alias field in SpecBlockAssociation and ScriptTemplateAssociation
    can be used to re-define how those are called out within the
    context of a Specification
    """

    __tablename__ = "specification"
    class_string = "specification"

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
        await session.refresh(self, attribute_names=["block_assocs_"])
        for block_assoc_ in self.block_assocs_:
            if block_assoc_.alias == spec_block_name:
                await session.refresh(block_assoc_, attribute_names=["spec_block_"])
                return block_assoc_.spec_block_
            # No overrides defined locally, just use the main table
        try:
            spec_block = await SpecBlock.get_row_by_fullname(session, spec_block_name)
            return spec_block
        except KeyError as msg:
            raise CMSpecficiationError(f"Could not find spec_block {spec_block_name} in {self}") from msg

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
        await session.refresh(self, attribute_names=["script_template_assocs_"])
        for script_template_assoc_ in self.script_template_assocs_:
            if script_template_assoc_.alias == script_template_name:
                await session.refresh(script_template_assoc_, attribute_names=["script_template_"])
                return script_template_assoc_.script_template_
            # No overrides defined locally, just use the main table
        try:
            script_template = await ScriptTemplate.get_row_by_fullname(session, script_template_name)
            return script_template
        except KeyError as msg:
            raise CMSpecficiationError(
                f"Could not find ScriptTemplate {script_template_name} in {self}",
            ) from msg
