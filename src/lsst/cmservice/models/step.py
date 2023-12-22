"""Pydantic model for the Step tables

These tables don't have anything beyond
standard Element columns
"""

from .element import ElementCreateMixin, ElementMixin


class StepCreate(ElementCreateMixin):
    """Parameters that are used to create new rows but not in DB tables"""


class Step(ElementMixin):
    """Parameters that are in DB tables and not used to create new rows"""

    class Config:
        orm_mode = True
