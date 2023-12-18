"""Pydantic model for the Step tables

These tables don't have anything beyond
standard Element columns
"""

from .element import ElementCreateMixin, ElementMixin, ElementUpdate


class StepCreate(ElementCreateMixin):
    """Parameters that are used to create new rows but not in DB tables"""

    # Name of the SpecBlock
    spec_block_name: str | None = None


class Step(ElementMixin):
    """Parameters that are in DB tables and not used to create new rows"""

    # ForeignKey for SpecBlock
    spec_block_id: int

    class Config:
        orm_mode = True


class StepUpdate(ElementUpdate):
    """Parameters that can be udpated"""
