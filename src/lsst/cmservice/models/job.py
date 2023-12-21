"""Pydantic model for the Job tables

These tables have a few columns beyond the
standard Element columns
"""
from .element import ElementBase, ElementCreateMixin, ElementMixin


class JobBase(ElementBase):
    """Parameters that are in DB tables and also used to create new rows"""

    attempt: int = 0
    wms_job_id: str | None = None
    stamp_url: str | None = None


class JobCreate(JobBase, ElementCreateMixin):
    """Parameters that are used to create new rows but not in DB tables"""

    pass


class Job(JobBase, ElementMixin):
    """Parameters that are in DB tables and not used to create new rows"""

    pass
