"""Pydantic model for the Group tables

These tables don't have anything beyond
standard Element columns
"""

from typing import ClassVar

from ..common.enums import LevelEnum
from .element import ElementCreateMixin, ElementMixin, ElementUpdate


class GroupCreate(ElementCreateMixin):
    """Parameters that are used to create new rows but not in DB tables"""

    # Name of the SpecBlock
    spec_block_name: str | None = None


class Group(ElementMixin):
    """Parameters that are in DB tables and not used to create new rows"""

    level: ClassVar = LevelEnum.group

    # ForeignKey for SpecBlock
    spec_block_id: int


class GroupUpdate(ElementUpdate):
    """Parameters that can be udpated"""
