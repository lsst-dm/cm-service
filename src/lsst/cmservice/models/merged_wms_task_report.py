from __future__ import annotations

from pydantic import BaseModel


class MergedWmsTaskReport(BaseModel):
    name: str

    n_expected: int
    n_unknown: int
    n_misfit: int
    n_unready: int
    n_ready: int
    n_pending: int
    n_running: int
    n_deleted: int
    n_held: int
    n_succeeded: int
    n_failed: int
    n_pruned: int

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
    reports: dict[str, MergedWmsTaskReport]

    def __iadd__(self, other: MergedWmsTaskReportDict) -> MergedWmsTaskReportDict:
        for key, val in other.reports.items():
            if key in self.reports:
                self.reports[key] += val
            else:
                self.reports[key] = val
        return self
