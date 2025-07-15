from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .handler import Handler
from .row import RowMixin

if TYPE_CHECKING:
    from ..common.types import AnyAsyncSession


class SpecBlock(Base, RowMixin):
    """Database table to manage blocks that are used to build campaigns

    A 'SpecBlock' is tagged fragment of a yaml file that specifies how
    to build an element of a campaign
    """

    __tablename__ = "spec_block"
    class_string = "spec_block"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(index=True)
    handler: Mapped[str | None] = mapped_column()
    data: Mapped[dict] = mapped_column(type_=JSON, default=dict)
    collections: Mapped[dict | None] = mapped_column(type_=JSON)
    child_config: Mapped[dict | None] = mapped_column(type_=JSON)
    spec_aliases: Mapped[dict | None] = mapped_column(type_=JSON)
    scripts: Mapped[dict | list | None] = mapped_column(type_=JSON)
    steps: Mapped[dict | list | None] = mapped_column(type_=JSON)

    col_names_for_table = ["id", "name", "handler"]

    @hybrid_property
    def fullname(self) -> str:
        """Maps name to fullname for consistency"""
        return self.name

    def __repr__(self) -> str:
        return f"SpecBlock {self.id}: {self.fullname} {self.data}"

    @classmethod
    async def get_create_kwargs(
        cls,
        session: AnyAsyncSession,
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
            "spec_aliases": kwargs.get("spec_aliases", {}),
            "scripts": kwargs.get("scripts", {}),
            "steps": kwargs.get("steps", {}),
        }

    @classmethod
    async def _delete_hook(
        cls,
        session: AnyAsyncSession,
        row_id: int,
    ) -> None:
        Handler.remove_from_cache(row_id)
