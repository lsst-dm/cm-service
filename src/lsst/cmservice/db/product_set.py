from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from .base import Base
from .job import Job
from .row import RowMixin

if TYPE_CHECKING:
    from .task_set import TaskSet


class ProductSet(Base, RowMixin):
    """Count by status of numbers of files of a particular type"""

    __tablename__ = "product_set"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("task_set.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column()
    fullname: Mapped[str] = mapped_column(unique=True)

    n_expected: Mapped[int] = mapped_column()
    n_done: Mapped[int] = mapped_column(default=0)
    n_failed: Mapped[int] = mapped_column(default=0)
    n_failed_upstream: Mapped[int] = mapped_column(default=0)
    n_missing: Mapped[int] = mapped_column(default=0)

    job_: Mapped["Job"] = relationship("Job", viewonly=True)
    task_: Mapped["TaskSet"] = relationship("TaskSet", viewonly=True)

    col_names_for_table = [
        "id",
        "fullname",
        "n_expected",
        "n_done",
        "n_failed",
        "n_failed_upstream",
        "n_missing",
    ]
