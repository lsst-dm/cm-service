"""Pydantic model for the Campaign tables

These tables don't have anything beyond
standard Element columns
"""

from .element import ElementCreateMixin, ElementMixin, ElementUpdate


class CampaignCreate(ElementCreateMixin):
    """Parameters that are used to create new rows but not in DB tables"""

    # Name of the SpecBlockAssociation
    spec_block_assoc_name: str | None = None


class Campaign(ElementMixin):
    """Parameters that are in DB tables and not used to create new rows"""

    # ForeignKey for SpecBlockAssociation
    spec_block_assoc_id: int

    class Config:
        orm_mode = True


class CampaignUpdate(ElementUpdate):
    """Parameters that can be udpated"""
