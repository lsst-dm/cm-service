from __future__ import annotations

from pydantic import BaseModel


class MergedProductSet(BaseModel):
    name: str

    n_expected: int
    n_failed: int
    n_failed_upstream: int
    n_missing: int
    n_done: int

    class Config:
        orm_mode = True

    def __iadd__(self, other: MergedProductSet) -> MergedProductSet:
        self.n_expected += other.n_expected
        self.n_failed += other.n_failed
        self.n_failed_upstream += other.n_failed_upstream
        self.n_missing += other.n_missing
        self.n_done += other.n_done
        return self

    def merge(self, other: MergedProductSet) -> MergedProductSet:
        self.n_failed = other.n_failed
        self.n_failed_upstream = other.n_failed_upstream
        self.n_missing = other.n_missing
        self.n_done += other.n_done
        return self


class MergedProductSetDict(BaseModel):
    reports: dict[str, MergedProductSet]

    def __iadd__(self, other: MergedProductSetDict) -> MergedProductSetDict:
        for key, val in other.reports.items():
            if key in self.reports:
                self.reports[key] += val
            else:
                self.reports[key] = val
        return self

    def merge(self, other: MergedProductSetDict) -> MergedProductSetDict:
        for key, val in other.reports.items():
            if key in self.reports:
                self.reports[key].merge(val)
            else:
                self.reports[key] = val
        return self
