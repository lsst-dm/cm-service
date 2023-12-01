from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import yaml
from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from .base import Base
from .row import RowMixin

if TYPE_CHECKING:
    from .specification import Specification


class ScriptTemplate(Base, RowMixin):
    """Database table to manage script templates

    A 'ScriptTemplate' is a template that gets used to create a bash script
    """

    __tablename__ = "script_template"

    id: Mapped[int] = mapped_column(primary_key=True)
    spec_id: Mapped[int] = mapped_column(ForeignKey("specification.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(index=True)
    fullname: Mapped[str] = mapped_column(unique=True)
    data: Mapped[dict | list | None] = mapped_column(type_=JSON)

    spec_: Mapped[Specification] = relationship("Specification", viewonly=True)

    def __repr__(self) -> str:
        return f"ScriptTemplate {self.id}: {self.fullname} {self.data}"

    col_names_for_table = ["id", "fullname"]

    @classmethod
    async def get_create_kwargs(
        cls,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> dict:
        spec_id = kwargs["spec_id"]
        spec_name = kwargs["spec_name"]
        name = kwargs["name"]

        return {
            "spec_id": spec_id,
            "name": name,
            "fullname": f"{spec_name}#{name}",
            "data": kwargs.get("data", None),
        }

    @classmethod
    async def load(  # pylint: disable=too-many-arguments
        cls,
        session: async_scoped_session,
        name: str,
        spec_id: int,
        spec_name: str,
        file_path: str,
    ) -> ScriptTemplate:
        """Load a ScriptTemplate from a file

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        name: str,
            Name for the ScriptTemplate

        spec_name: str,
            Name for the specification

        file_path
            Path to the file

        Returns
        -------
        script_template : `ScriptTemplate`
            Newly created `ScriptTemplate`
        """
        full_file_path = os.path.abspath(os.path.expandvars(file_path))
        with open(full_file_path, encoding="utf-8") as fin:
            data = yaml.safe_load(fin)

        return await cls.create_row(session, name=name, spec_id=spec_id, spec_name=spec_name, data=data)
