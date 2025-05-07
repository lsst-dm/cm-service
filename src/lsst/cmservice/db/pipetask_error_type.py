import re
from typing import TYPE_CHECKING

from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import UniqueConstraint

from ..common.enums import ErrorActionEnum, ErrorFlavorEnum, ErrorSourceEnum
from .base import Base
from .row import RowMixin

if TYPE_CHECKING:
    from .pipetask_error import PipetaskError


class PipetaskErrorType(Base, RowMixin):
    """Database table to keep track of types of errors from Pipetask tasks"""

    __tablename__ = "pipetask_error_type"
    class_string = "pipetask_error_type"

    __table_args__ = (UniqueConstraint("task_name", "diagnostic_message"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    error_source: Mapped[ErrorSourceEnum] = mapped_column()
    error_flavor: Mapped[ErrorFlavorEnum] = mapped_column()
    error_action: Mapped[ErrorActionEnum] = mapped_column()
    task_name: Mapped[str] = mapped_column()
    diagnostic_message: Mapped[str] = mapped_column()

    errors_: Mapped[list["PipetaskError"]] = relationship("PipetaskError", viewonly=True)

    @hybrid_property
    def fullname(self) -> str:
        return self.task_name + "#" + self.diagnostic_message

    col_names_for_table = [
        "id",
        "task_name",
        "diagnostic_message",
        "error_source",
        "error_action",
        "error_flavor",
    ]

    def __repr__(self) -> str:
        return f"Id={self.id}\n    {self.diagnostic_message:.149}"

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
