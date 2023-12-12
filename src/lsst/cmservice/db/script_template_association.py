from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from .base import Base
from .row import RowMixin
from .script_template import ScriptTemplate
from .specification import Specification


class ScriptTemplateAssociation(Base, RowMixin):
    """Database table to manage connections between
    ScriptTemplatess and Specifications
    """

    __tablename__ = "script_template_association"
    class_string = "script_template_association"

    id: Mapped[int] = mapped_column(primary_key=True)
    spec_id: Mapped[int] = mapped_column(ForeignKey("specification.id", ondelete="CASCADE"), index=True)
    script_template_id: Mapped[int] = mapped_column(
        ForeignKey("script_template.id", ondelete="CASCADE"),
        index=True,
    )
    alias: Mapped[str] = mapped_column()
    fullname: Mapped[str] = mapped_column(unique=True)

    spec_: Mapped[Specification] = relationship("Specification", viewonly=True)
    script_template_: Mapped[ScriptTemplate] = relationship("ScriptTemplate", viewonly=True)

    col_names_for_table = ["id", "fullname", "script_template_id"]

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
            "fullname": f"{spec_name}#{alias}",
        }
        return ret_dict
