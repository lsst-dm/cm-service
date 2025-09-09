from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column

from ..common.errors import CMMissingFullnameError, CMSpecificationError
from .base import Base
from .row import RowMixin
from .spec_block import SpecBlock

if TYPE_CHECKING:
    from ..common.types import AnyAsyncSession


class Specification(Base, RowMixin):
    """Database table to manage mapping and grouping SpecBlocks
    by associating them to a Specification
    """

    __tablename__ = "specification"
    class_string = "specification"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(index=True)
    data: Mapped[dict] = mapped_column(type_=JSON, default=dict)
    child_config: Mapped[dict | list | None] = mapped_column(type_=JSON)
    collections: Mapped[dict | list | None] = mapped_column(type_=JSON)
    spec_aliases: Mapped[dict | None] = mapped_column(type_=JSON)

    col_names_for_table = ["id", "name"]

    @hybrid_property
    def fullname(self) -> str:
        """Maps name to fullname for consistency"""
        return self.name

    def __repr__(self) -> str:
        return f"Spec. {self.id}: {self.name}"

    async def get_block(
        self,
        session: AnyAsyncSession,
        spec_block_name: str,
    ) -> SpecBlock:
        """Get a SpecBlock associated to this Specification

        Parameters
        ----------
        session: AnyAsyncSession
            DB session manager

        spec_block_name: str
            Name of the SpecBlock to return

        Returns
        -------
        spec_block: SpecBlock
            Requested SpecBlock
        """
        try:
            await session.refresh(self, attribute_names=["spec_aliases"])
            aliases = self.spec_aliases if isinstance(self.spec_aliases, dict) else {}
            spec_block = await SpecBlock.get_row_by_fullname(
                session,
                aliases.get(spec_block_name, spec_block_name),
            )
            return spec_block
        except CMMissingFullnameError as e:
            msg = f"Could not find spec_block {spec_block_name} in {self}"
            raise CMSpecificationError(msg) from e
