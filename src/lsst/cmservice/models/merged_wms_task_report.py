from __future__ import annotations

from pydantic import BaseModel


class MergedWmsTaskReport(BaseModel):  # pylint: disable=too-many-instance-attributes
    """Pydantic model for combining data on WmsTasks"""

    name: str

    n_expected: int = 0
    n_unknown: int = 0
    n_misfit: int = 0
    n_unready: int = 0
    n_ready: int = 0
    n_pending: int = 0
    n_running: int = 0
    n_deleted: int = 0
    n_held: int = 0
    n_succeeded: int = 0
    n_failed: int = 0
    n_pruned: int = 0

    class Config:
        orm_mode = True

    def __iadd__(self, other: MergedWmsTaskReport) -> MergedWmsTaskReport:
        self.n_expected += other.n_expected
        self.n_unknown += other.n_unknown
        self.n_misfit += other.n_misfit
        self.n_unready += other.n_unready
        self.n_ready += other.n_ready
        self.n_pending += other.n_pending
        self.n_running += other.n_running
        self.n_deleted += other.n_deleted
        self.n_held += other.n_held
        self.n_succeeded += other.n_succeeded
        self.n_failed += other.n_failed
        self.n_pruned += other.n_pruned
        return self


class MergedWmsTaskReportDict(BaseModel):
    """Pydantic model for combining data on sets of WmsTasks"""

    reports: dict[str, MergedWmsTaskReport]

    def __iadd__(self, other: MergedWmsTaskReportDict) -> MergedWmsTaskReportDict:
        for key, val in other.reports.items():
            if key in self.reports:
                self.reports[key] += val
            else:
                self.reports[key] = val
        return self
