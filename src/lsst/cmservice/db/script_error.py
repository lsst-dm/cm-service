from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from ..common.enums import ErrorSourceEnum
from .base import Base
from .enums import SqlErrorSourceEnum
from .row import RowMixin
from .script import Script


class ScriptError(Base, RowMixin):
    """Database table to keep track of errors from running `Scripts`"""

    __tablename__ = "script_error"
    class_string = "script_error"

    id: Mapped[int] = mapped_column(primary_key=True)
    script_id: Mapped[int | None] = mapped_column(ForeignKey("script.id", ondelete="CASCADE"), index=True)
    source: Mapped[ErrorSourceEnum] = mapped_column(type_=SqlErrorSourceEnum)
    diagnostic_message: Mapped[str] = mapped_column()

    script_: Mapped["Script"] = relationship("Script", viewonly=True)

    col_names_for_table = ["id", "script_id", "source"]

    def __repr__(self) -> str:
        s = f"Id={self.id} {self.script_id}\n"
        if len(self.diagnostic_message) > 150:
            diag_message = self.diagnostic_message[0:150]
        else:
            diag_message = self.diagnostic_message
        s += f"    {diag_message}"
        return s
