from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from ..common.enums import ErrorSourceEnum
from .base import Base
from .row import RowMixin
from .script import Script


class ScriptError(Base, RowMixin):
    """Database table to keep track of errors from running `Scripts`"""

    __tablename__ = "script_error"
    class_string = "script_error"

    id: Mapped[int] = mapped_column(primary_key=True)
    script_id: Mapped[int | None] = mapped_column(ForeignKey("script.id", ondelete="CASCADE"), index=True)
    source: Mapped[ErrorSourceEnum] = mapped_column()
    diagnostic_message: Mapped[str] = mapped_column()

    script_: Mapped["Script"] = relationship("Script", viewonly=True)

    col_names_for_table = ["id", "script_id", "source"]

    def __repr__(self) -> str:
        return f"Id={self.id} {self.script_id}\n    {self.diagnostic_message:.150}"
