"""Pydantic model for the Campaign tables

These tables don't have anything beyond
standard Element columns
"""

from .element import ElementCreateMixin, ElementMixin


class CampaignCreate(ElementCreateMixin):
    """Parameters that are used to create new rows but not in DB tables"""

    pass


class Campaign(ElementMixin):
    """Parameters that are in DB tables and not used to create new rows"""

    class Config:
        orm_mode = True
