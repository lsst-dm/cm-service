"""Module for API models related to the Schedule interface.

This module includes API request and response models that are not otherwise
part of the ORM database model hierarchy.
"""

from typing import Annotated

from pydantic import BaseModel, Field, StrictBool


class ScheduleUpdate(BaseModel):
    """Model representing updatable fields for a PATCH operation on a
    Schedule."""

    cron: str | None = None
    is_enabled: StrictBool | None = None
    metadata: Annotated[dict, Field(default_factory=dict)]
