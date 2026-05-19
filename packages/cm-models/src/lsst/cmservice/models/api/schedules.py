"""Module for API models related to the Schedule interface.

This module includes API request and response models that are not otherwise
part of the ORM database model hierarchy.
"""

from typing import Annotated

from pydantic import BaseModel, Field, StrictBool

from .manifests import Manifest, ManifestSpec


class ScheduleConfiguration(ManifestSpec):
    """Model representing the configuration details of a Schedule."""

    # NOTE migrations targeting this configuration model (adding or changing
    # fields, e.g.) must either always use a backward-compatible default and/or
    # be matched with an alembic migration to backfill a backward-compatible
    # default for all extant records.
    expressions: dict[str, str] = Field(
        default_factory=dict,
        description="A mapping of a variable name to a string representation of a valid Python expression.",
        examples=[{"today": "datetime.now()"}],
    )
    auto_start: bool = Field(
        default=True, description="Whether the new campaign will be created in a paused or running state."
    )
    name_format: str = Field(
        default="%Y%m%d",
        description="A datetime format string used to format the nonce added to the campaign name.",
    )
    cron: str = Field(
        default="0 0 1-7 * SUN",
        description="A crontab string expressing a scheduling cadence.",
    )


class ScheduleUpdate(BaseModel):
    """Model representing updatable fields for a PATCH operation on a
    Schedule."""

    cron: str | None = None
    is_enabled: StrictBool | None = None
    configuration: Annotated[dict, Field(default_factory=dict)]
    next_run_at: str | None = None


class ScheduleMetadata(BaseModel):
    """A metadata model for Schedule manifests"""

    owner: str = "root"


class ScheduleManifest(Manifest[ScheduleMetadata, ScheduleConfiguration]):
    """A Manifest for a Schedule consistent with the desing of other campaign
    element API objects.
    """

    ...
