from __future__ import annotations

from copy import deepcopy

from pydantic import BaseModel, ConfigDict


class MergedProductSet(BaseModel):
    """Pydantic model for combining data on Products"""

    model_config = ConfigDict(from_attributes=True)

    name: str

    n_expected: int = 0
    n_failed: int = 0
    n_failed_upstream: int = 0
    n_missing: int = 0
    n_done: int = 0

    def __iadd__(self, other: MergedProductSet) -> MergedProductSet:
        self.n_expected += other.n_expected
        self.n_failed += other.n_failed
        self.n_failed_upstream += other.n_failed_upstream
        self.n_missing += other.n_missing
        self.n_done += other.n_done
        return self

    def merge(self, other: MergedProductSet) -> MergedProductSet:
        """Merge in another MergedProductSet

        This is used when combining retries in a single Group
        """
        self.n_failed = other.n_failed
        self.n_failed_upstream = other.n_failed_upstream
        self.n_missing = other.n_missing
        self.n_done += other.n_done
        self.n_expected = self.n_failed + self.n_failed_upstream + self.n_missing + self.n_done
        return self


class MergedProductSetDict(BaseModel):
    """Pydantic model for combining data on sets of Products"""

    reports: dict[str, MergedProductSet]

    def __iadd__(self, other: MergedProductSetDict) -> MergedProductSetDict:
        for key, val in other.reports.items():
            if key in self.reports:
                self.reports[key] += val
            else:
                self.reports[key] = deepcopy(val)
        return self

    def merge(self, other: MergedProductSetDict) -> MergedProductSetDict:
        """Merge in another MergedProductSetDict

        This is used when combining retries in a single Group
        """
        for key, val in other.reports.items():
            if key in self.reports:
                self.reports[key].merge(val)
            else:
                self.reports[key] = deepcopy(val)
        return self
