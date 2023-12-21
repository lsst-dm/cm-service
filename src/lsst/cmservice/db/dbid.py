from __future__ import annotations

from dataclasses import dataclass

from ..common.enums import LevelEnum


@dataclass
class DbId:
    """Information to identify a single entry in the CM database tables"""

    _level: LevelEnum  # Which table
    _id: int  # Primary key in that table

    def __repr__(self) -> str:
        return f"DbId({self._level.name}:{self._id})"

    @property
    def level(self) -> LevelEnum:
        """Returns LevelEnum of row"""
        return self._level

    @property
    def id(self) -> int:
        """Returns ID of row"""
        return self._id
