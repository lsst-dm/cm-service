from __future__ import annotations

from copy import deepcopy

from pydantic import BaseModel, ConfigDict


class MergedTaskSet(BaseModel):
    """Pydantic model for combining data on Tasks"""

    model_config = ConfigDict(from_attributes=True)

    name: str

    n_expected: int = 0
    n_failed: int = 0
    n_failed_upstream: int = 0
    n_done: int = 0

    def __iadd__(self, other: MergedTaskSet) -> MergedTaskSet:
        self.n_expected += other.n_expected
        self.n_failed += other.n_failed
        self.n_failed_upstream += other.n_failed_upstream
        self.n_done += other.n_done
        return self

    def merge(self, other: MergedTaskSet) -> MergedTaskSet:
        """Merge in another MergedTaskSet

        This is used when combining retries in a single Group
        """
        self.n_failed = other.n_failed
        self.n_failed_upstream = other.n_failed_upstream
        self.n_done += other.n_done
        return self


class MergedTaskSetDict(BaseModel):
    """Pydantic model for combining data on sets of Tasks"""

    reports: dict[str, MergedTaskSet]

    def __iadd__(self, other: MergedTaskSetDict) -> MergedTaskSetDict:
        for key, val in other.reports.items():
            if key in self.reports:
                self.reports[key] += val
            else:
                self.reports[key] = deepcopy(val)
        return self

    def merge(self, other: MergedTaskSetDict) -> MergedTaskSetDict:
        """Merge in another MergedTaskSetDict

        This is used when combining retries in a single Group
        """
        for key, val in other.reports.items():
            if key in self.reports:
                self.reports[key].merge(val)
            else:
                self.reports[key] = deepcopy(val)
        return self
