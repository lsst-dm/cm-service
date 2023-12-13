import re
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..common.enums import ErrorActionEnum, ErrorFlavorEnum, ErrorSourceEnum
from .base import Base
from .enums import SqlErrorActionEnum, SqlErrorFlavorEnum, SqlErrorSourceEnum
from .row import RowMixin

if TYPE_CHECKING:
    from .pipetask_error import PipetaskError


class PipetaskErrorType(Base, RowMixin):
    """Database table to keep track of types of errors from Pipetask tasks"""

    __tablename__ = "pipetask_error_type"
    class_string = "pipetask_error_type"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[ErrorSourceEnum] = mapped_column(type_=SqlErrorSourceEnum)
    flavor: Mapped[ErrorFlavorEnum] = mapped_column(type_=SqlErrorFlavorEnum)
    action: Mapped[ErrorActionEnum] = mapped_column(type_=SqlErrorActionEnum)
    task_name: Mapped[str] = mapped_column()
    diagnostic_message: Mapped[str] = mapped_column(unique=True)

    errors_: Mapped[list["PipetaskError"]] = relationship("PipetaskError", viewonly=True)

    col_names_for_table = ["id", "task_name", "diagnostic_message", "source", "action", "flavor"]

    def __repr__(self) -> str:
        s = f"Id={self.id}\n"
        if len(self.diagnostic_message) > 150:
            diag_message = self.diagnostic_message[0:149]
        else:
            diag_message = self.diagnostic_message
        s += f"    {diag_message}"
        return s

    def match(
        self,
        task_name: str,
        diagnostic_message: str,
    ) -> bool:
        """Test if a PipetaskError matches this PipetaskErrorType

        Parameters
        ----------
        task_name: str
            Name of the Pipetask task that had the Error

        diagnostic_message: str
            Message to match against the regexp template

        Returns
        -------
        match : bool
            True if the PipetaskError matches this PipetaskErrorType
        """
        if not re.match(self.task_name.strip(), task_name.strip()):
            return False
        if not re.match(self.diagnostic_message.strip(), diagnostic_message.strip()):
            return False
        return True
