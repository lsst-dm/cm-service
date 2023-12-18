"""Pydantic model for the Job tables

These tables have a few columns beyond the
standard Element columns
"""
from .element import ElementBase, ElementCreateMixin, ElementMixin, ElementUpdate


class JobBase(ElementBase):
    """Parameters that are in DB tables and also used to create new rows"""

    attempt: int = 0
    wms_job_id: str | None = None
    stamp_url: str | None = None


class JobCreate(JobBase, ElementCreateMixin):
    """Parameters that are used to create new rows but not in DB tables"""

    # Name of the SpecBlock
    spec_block_name: str | None = None


class Job(JobBase, ElementMixin):
    """Parameters that are in DB tables and not used to create new rows"""

    # ForeignKey for SpecBlock
    spec_block_id: int


class JobUpdate(ElementUpdate):
    """Parameters that can be udpated"""

    wms_job_id: str | None = None
    stamp_url: str | None = None
