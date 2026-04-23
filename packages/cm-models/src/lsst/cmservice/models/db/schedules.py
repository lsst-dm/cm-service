"""Module for Database model definitions for the CM Service schedules and
related tables.
"""

import re
from typing import Annotated
from uuid import uuid4

from pydantic import UUID4, AwareDatetime, BeforeValidator, StrictBool
from pydantic_extra_types.cron import CronStr
from sqlalchemy import UniqueConstraint
from sqlmodel import Column, DateTime, Enum, Field, Relationship

from ..enums import ManifestKind
from ..types import KindField
from .base import BaseSQLModel
from .campaigns import jsonb_column


def check_manifest_template_string(value: str) -> str:
    """Validator for a manifest template string as included in one of the
    `ManifestTemplateBase`-derived models.

    Requests that fail this validator should be returned to the caller with a
    422 (Unprocessable Entity) code.
    """
    # Because we can't really parse or load the template string directly as a
    # python object (it might have Jinja control elements, etc.), we instead
    # just check for the presence of known bad contents.

    if re.search(r"kind:\s*(start|end)", value.lower()):
        raise ValueError("Start or End node kinds are not allowed in a template manifest.")
    return value


class ScheduleBase(BaseSQLModel):
    """schedules_v2 base model, used to create new schedule objects."""

    id: UUID4 = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(description="A unique name for this schedule")
    cron: CronStr = Field(description="A cron expression string")
    metadata_: dict = jsonb_column("metadata", aliases=["metadata", "metadata_"])
    configuration: dict = jsonb_column("configuration")
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
    """A validating model for the schedule API.

    Note: When this model is used to create an ORM object, any overlapping or
    incompatible fields are explictly excluded from serialization.
    """

    templates: list["CreateManifestTemplate"] = Field(default_factory=list, exclude=True)


class ManifestTemplateBase(BaseSQLModel):
    """templates_v2 base model, used to create new manifest template objects"""

    id: UUID4 = Field(default_factory=uuid4, primary_key=True)
    version: int = Field(default=1)
    kind: KindField = Field(
        sa_column=Column("kind", Enum(ManifestKind, length=20, native_enum=False, create_constraint=False)),
    )
    manifest: str = ""
    metadata_: dict = jsonb_column("metadata", aliases=["metadata", "metadata_"])


class ManifestTemplate(ManifestTemplateBase, table=True):
    """Model used for database operations involving templates_v2 table rows"""

    model_config = {"validate_assignment": True}
    __tablename__: str = "templates_v2"  # type: ignore[misc]
    schedule_id: UUID4 = Field(foreign_key="schedules_v2.id", ondelete="CASCADE")


class CreateManifestTemplate(ManifestTemplateBase):
    """A validating model for manifest templates in the schedule API."""

    # This model differs from its sibling in that the schedule_id is optional
    # rather than a mandatory FK constraint, allowing it to be used to
    # create new ManifestTemplate objects.
    schedule_id: UUID4 | None = None
    manifest: Annotated[str, BeforeValidator(check_manifest_template_string)] = ""
