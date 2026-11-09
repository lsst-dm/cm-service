"""Module for API models related to the Schedule interface.

This module includes API request and response models that are not otherwise
part of the ORM database model hierarchy.
"""

from typing import Annotated, Any

from pydantic import UUID4, BaseModel, Field, StrictBool

from ..types import TemplateExpressions
from .manifests import Manifest, ManifestSpec


class ScheduleTriggerBinding(BaseModel):
    """Model representing an event source that triggers a oneshot of a
    Schedule, and the protocol a message from the source must satisfy to do
    so.
    """

    source: str = Field(description="The kind of event source, e.g., `kafka`.", examples=["kafka"])
    channel: str = Field(
        description="The channel of the event source on which the trigger events are delivered, e.g., a "
        "Kafka topic.",
        examples=["cm-topic"],
    )
    protocol: str = Field(
        min_length=1,
        description="A JMESPath query applied to the JSON message, which evaluates to `null` for a message "
        "that does not trigger the schedule, or otherwise to an object of the scalar values that override "
        "the values of the schedule's expressions for the triggered oneshot.",
        examples=["(type=='prompt_processing' && state=='complete') && detail.{day_obs: day_obs} || `null`"],
    )


class ScheduleConfiguration(ManifestSpec):
    """Model representing the configuration details of a Schedule."""

    # NOTE migrations targeting this configuration model (adding or changing
    # fields, e.g.) must either always use a backward-compatible default and/or
    # be matched with an alembic migration to backfill a backward-compatible
    # default for all extant records.
    expressions: TemplateExpressions = Field(
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
    trigger: ScheduleTriggerBinding | None = Field(
        default=None,
        description="A trigger event sources for the schedule (not counting `cron` or `oneshot`)",
    )
    uri: str | None = Field(
        default=None,
        description="An external URI from which the campaign template should be loaded.",
        examples=["https://raw.githubusercontent.com/lsst/repo/refs/heads/main/cm_campaign.yaml"],
    )


class ScheduleUpdate(BaseModel):
    """Model representing updatable fields for a PATCH operation on a
    Schedule."""

    cron: str | None = None
    is_enabled: StrictBool | None = None
    configuration: Annotated[dict, Field(default_factory=dict)]
    next_run_at: str | None = None


class ScheduleOneshot(BaseModel):
    """Model representing the optional request body of a oneshot operation on
    a Schedule.
    """

    expressions: TemplateExpressions = Field(
        default_factory=dict,
        description=(
            "A mapping of a variable name to a string representation of a valid Python expression. "
            "These expressions override or extend the schedule's own expressions for this oneshot only."
        ),
        examples=[{"yesterday": "datetime(2026, 11, 1, tzinfo=timezone.utc)"}],
    )


class ScheduleTrigger(BaseModel):
    """Model describing the provenance of a campaign created by a oneshot
    operation on a Schedule.

    A serialized trigger, without its overrides, is stored in the new
    campaign's metadata under the ``trigger`` key. When a ``key`` is present,
    it is used to detect duplicate triggers of the same schedule, i.e., an
    idempotency key.
    """

    source: str = Field(description="The mechanism that triggered the oneshot, e.g., `api`.")
    actor: str = Field(default="root", description="The user or service responsible for the trigger.")
    schedule: UUID4 = Field(description="The id of the triggered schedule.")
    key: str | None = Field(default=None, description="An idempotency key for the trigger.")
    overrides: dict[str, Any] = Field(
        default_factory=dict,
        description="Values that override or extend the values of the schedule's own expressions.",
    )

    def containment(self) -> dict:
        """Returns a mapping suitable for a JSONB containment query against a
        campaign's metadata, matching any campaign created by an equivalent
        trigger.
        """
        return {"trigger": {"schedule": str(self.schedule), "key": self.key}}


class ScheduleMetadata(BaseModel):
    """A metadata model for Schedule manifests"""

    owner: str = "root"


class ScheduleManifest(Manifest[ScheduleMetadata, ScheduleConfiguration]):
    """A Manifest for a Schedule consistent with the design of other campaign
    element API objects.
    """

    ...
