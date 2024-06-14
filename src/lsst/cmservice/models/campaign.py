"""Pydantic model for the Campaign tables

These tables don't have anything beyond
standard Element columns
"""

from pydantic import ConfigDict

from .element import ElementCreateMixin, ElementMixin, ElementUpdate


class CampaignCreate(ElementCreateMixin):
    """Parameters that are used to create new rows but not in DB tables"""

    # Combined name of Specification and SpecBlock
    spec_block_assoc_name: str | None = None


class Campaign(ElementMixin):
    """Parameters that are in DB tables and not used to create new rows"""

    model_config = ConfigDict(from_attributes=True)

    # ForeignKey for Specification
    spec_id: int

    # ForeignKey for SpecBlock
    spec_block_id: int


class CampaignUpdate(ElementUpdate):
    """Parameters that can be udpated"""
