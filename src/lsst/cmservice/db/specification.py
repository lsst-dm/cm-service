from __future__ import annotations


from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column

from ..common.errors import CMSpecficiationError
from .base import Base
from .row import RowMixin
from .script_template import ScriptTemplate
from .spec_block import SpecBlock


class Specification(Base, RowMixin):
    """Database table to manage mapping and grouping of SpecBlock
    and ScriptTemplate by associating them to a Specification
    """

    __tablename__ = "specification"
    class_string = "specification"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(index=True)
    data: Mapped[dict | list | None] = mapped_column(type_=JSON)
    child_config: Mapped[dict | list | None] = mapped_column(type_=JSON)
    collections: Mapped[dict | list | None] = mapped_column(type_=JSON)
    spec_aliases: Mapped[dict | list | None] = mapped_column(type_=JSON)

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
        try:
            spec_block = await SpecBlock.get_row_by_fullname(session, spec_block_name)
            return spec_block
        except KeyError as msg:
            breakpoint()
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
        try:
            script_template = await ScriptTemplate.get_row_by_fullname(session, script_template_name)
            return script_template
        except KeyError as msg:
            raise CMSpecficiationError(
                f"Could not find ScriptTemplate {script_template_name} in {self}",
            ) from msg
