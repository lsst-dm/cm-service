"""Module for Database model definitions for the CM Service schedules and
related tables.
"""

from uuid import uuid4

from pydantic import UUID4, AwareDatetime, StrictBool
from pydantic_extra_types.cron import CronStr
from sqlalchemy import UniqueConstraint
from sqlmodel import Column, DateTime, Enum, Field, Relationship

from ..enums import ManifestKind
from ..types import KindField
from .base import BaseSQLModel
from .campaigns import jsonb_column


class ScheduleBase(BaseSQLModel):
    """schedules_v2 base model, used to create new schedule objects."""

    id: UUID4 = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(description="A unique name for this schedule")
    cron: CronStr = Field(description="A cron expression string")
    metadata_: dict = jsonb_column("metadata", aliases=["metadata", "metadata_"])
    expressions: dict = jsonb_column("expressions")
    is_enabled: StrictBool = Field(default=False)
    next_run_at: AwareDatetime | None = Field(
        default=None,
        description="The `datetime` (UTC) at which this Schedule must next execute",
        sa_column=Column(DateTime(timezone=True)),
    )
    last_run_at: AwareDatetime | None = Field(
        default=None,
        description="The `datetime` (UTC) at which this Schedule was last executed",
        sa_column=Column(DateTime(timezone=True)),
    )


class Schedule(ScheduleBase, table=True):
    """Model used for database operations involving schedule_v2 table rows"""

    model_config = {"validate_assignment": True}

    __tablename__: str = "schedules_v2"  # type: ignore[misc]
    __table_args__: tuple[UniqueConstraint, ...] = (UniqueConstraint("name", name="uq_schedule_name"),)  # type: ignore[assignment]

    # The templates virtual field is eagerly loaded (SELECT) by default!
    templates: list["ManifestTemplate"] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all,delete-orphan"},
    )


class CreateSchedule(ScheduleBase):
    """A validating model for the new schedule API.

    Note: When this model is used to create an ORM object, any overlapping or
    incompatible fields are explictly excluded from serialization.
    """

    templates: list["CreateManifestTemplate"] = Field(default_factory=list, exclude=True)


class ManifestTemplateBase(BaseSQLModel):
    """templates_v2 base model, used to create new manifest template objects"""

    id: UUID4 = Field(default_factory=uuid4, primary_key=True)
    kind: KindField = Field(
        sa_column=Column("kind", Enum(ManifestKind, length=20, native_enum=False, create_constraint=False)),
    )
    manifest: dict = jsonb_column("manifest")
    metadata_: dict = jsonb_column("metadata", aliases=["metadata", "metadata_"])


class ManifestTemplate(ManifestTemplateBase, table=True):
    """Model used for database operations involving templates_v2 table rows"""

    model_config = {"validate_assignment": True}
    __tablename__: str = "templates_v2"  # type: ignore[misc]
    schedule_id: UUID4 = Field(foreign_key="schedules_v2.id", ondelete="CASCADE")


class CreateManifestTemplate(ManifestTemplateBase):
    """A validating model for manifest templates in the new schedule API."""

    # This model differs from its sibling in that the schedule_id is optional
    # rather than a mandatory FK constraint, allowing it to be used to
    # create new ManifestTemplate objects.
    schedule_id: UUID4 | None = None
