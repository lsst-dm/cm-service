from typing import TYPE_CHECKING

from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from .base import Base
from .job import Job
from .row import RowMixin

if TYPE_CHECKING:
    from .pipetask_error_type import PipetaskErrorType
    from .task_set import TaskSet


class PipetaskError(Base, RowMixin):
    """Database table to keep track of individual errors from Pipetask tasks"""

    __tablename__ = "pipetask_error"
    class_string = "pipetask_error"

    id: Mapped[int] = mapped_column(primary_key=True)
    error_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipetask_error_type.id", ondelete="CASCADE"),
        index=True,
    )
    task_id: Mapped[int] = mapped_column(ForeignKey("task_set.id", ondelete="CASCADE"), index=True)
    quanta: Mapped[str] = mapped_column()
    diagnostic_message: Mapped[str] = mapped_column()
    data_id: Mapped[dict | list | None] = mapped_column(type_=JSON)

    job_: Mapped["Job"] = relationship(
        "Job",
        primaryjoin="TaskSet.id==PipetaskError.task_id",
        secondary="join(TaskSet, Job)",
        secondaryjoin="TaskSet.job_id==Job.id",
        viewonly=True,
    )
    task_: Mapped["TaskSet"] = relationship("TaskSet", viewonly=True)
    error_type_: Mapped["PipetaskErrorType"] = relationship("PipetaskErrorType", viewonly=True)

    col_names_for_table = ["id", "error_type_id", "task_id", "quanta", "data_id"]
