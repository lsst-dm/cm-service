import re
from typing import TYPE_CHECKING, List

from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..common.enums import ErrorAction, ErrorFlavor, ErrorSource
from .base import Base
from .row import RowMixin

if TYPE_CHECKING:
    from .pipetask_error import PipetaskError


class PipetaskErrorType(Base, RowMixin):
    """Database table to keep track of types of errors from Pipetask tasks"""

    __tablename__ = "error_type"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[ErrorSource] = mapped_column()
    flavor: Mapped[ErrorFlavor] = mapped_column()
    action: Mapped[ErrorAction] = mapped_column()
    task_name: Mapped[str] = mapped_column()
    diagnostic_message: Mapped[str] = mapped_column(unique=True)

    errors_: Mapped[List["PipetaskError"]] = relationship("PipetaskError", viewonly=True)

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
