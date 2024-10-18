"""Pydantic model for the Step tables

These tables don't have anything beyond
standard Element columns
"""

from typing import ClassVar

from pydantic import ConfigDict

from ..common.enums import LevelEnum
from .element import ElementCreateMixin, ElementMixin, ElementUpdate


class StepCreate(ElementCreateMixin):
    """Parameters that are used to create new rows but not in DB tables"""

    # Name of the SpecBlock
    spec_block_name: str | None = None


class Step(ElementMixin):
    """Parameters that are in DB tables and not used to create new rows"""

    level: ClassVar = LevelEnum.step

    model_config = ConfigDict(from_attributes=True)

    # ForeignKey for SpecBlock
    spec_block_id: int


class StepUpdate(ElementUpdate):
    """Parameters that can be udpated"""
