from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from .base import Base
from .row import RowMixin

if TYPE_CHECKING:
    from .job import Job
    from .product_set import ProductSet


class TaskSet(Base, RowMixin):
    """Count by status of numbers of task of a particular type"""

    __tablename__ = "task_set"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column()
    fullname: Mapped[str] = mapped_column(unique=True)

    n_expected: Mapped[int] = mapped_column()
    n_done: Mapped[int] = mapped_column(default=0)
    n_failed: Mapped[int] = mapped_column(default=0)
    n_failed_upstream: Mapped[int] = mapped_column(default=0)

    job_: Mapped["Job"] = relationship("Job", viewonly=True)
    products_: Mapped[list["ProductSet"]] = relationship("ProductSet", viewonly=True)
