from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from .base import Base
from .row import RowMixin

if TYPE_CHECKING:
    from .job import Job


class WmsTaskReport(Base, RowMixin):
    """Count by status of numbers of workflows task of a particular type"""

    __tablename__ = "wms_task_report"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column()
    fullname: Mapped[str] = mapped_column(unique=True)

    n_unknown: Mapped[int] = mapped_column(default=0)
    n_misfit: Mapped[int] = mapped_column(default=0)
    n_unready: Mapped[int] = mapped_column(default=0)
    n_ready: Mapped[int] = mapped_column(default=0)
    n_pending: Mapped[int] = mapped_column(default=0)
    n_running: Mapped[int] = mapped_column(default=0)
    n_deleted: Mapped[int] = mapped_column(default=0)
    n_held: Mapped[int] = mapped_column(default=0)
    n_succeeded: Mapped[int] = mapped_column(default=0)
    n_failed: Mapped[int] = mapped_column(default=0)
    n_pruned: Mapped[int] = mapped_column(default=0)

    job_: Mapped["Job"] = relationship("Job", viewonly=True)

    col_names_for_table = [
        "id",
        "fullname",
        "n_unknown",
        "n_misfit",
        "n_unready",
        "n_ready",
        "n_pending",
        "n_running",
        "n_deleted",
        "n_held",
        "n_succeeded",
        "n_failed",
        "n_pruned",
    ]
