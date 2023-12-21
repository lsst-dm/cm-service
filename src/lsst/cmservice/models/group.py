"""Pydantic model for the Group tables

These tables don't have anything beyond
standard Element columns
"""

from .element import ElementCreateMixin, ElementMixin


class GroupCreate(ElementCreateMixin):
    """Parameters that are used to create new rows but not in DB tables"""

    pass


class Group(ElementMixin):
    """Parameters that are in DB tables and not used to create new rows"""

    pass
