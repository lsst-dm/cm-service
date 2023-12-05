from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from .base import Base
from .row import RowMixin
from .spec_block import SpecBlock
from .specification import Specification


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

    col_names_for_table = ["id", "fullname", "spec_block_id"]

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
            "fullname": f"{spec_name}#{alias}",
        }
        return ret_dict
