"""Module for Database model definitions for the CM Service schedules and
related tables.
"""

import re
from typing import Annotated
from uuid import uuid4, uuid5

from pydantic import UUID4, UUID5, AwareDatetime, BeforeValidator, StrictBool, ValidationInfo, model_validator
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
    """templates_v2 base model, used to create new manifest template objects.

    The id of a manifest template is a UUID5, expected to be formed by hashing
    a string of form `NAME=...,KIND=...,VERSION=n` in the namespace of the
    `schedule_id`.
    """

    name: str
    version: int = Field(default=1)
    kind: KindField = Field(
        sa_column=Column("kind", Enum(ManifestKind, length=20, native_enum=False, create_constraint=False)),
    )
    manifest: str = ""
    metadata_: dict = jsonb_column("metadata", aliases=["metadata", "metadata_"])

    @model_validator(mode="before")
    @classmethod
    def custom_model_validator[T](cls, data: T, info: ValidationInfo) -> T:
        """Validates the model and provides computed default values when avail-
        able.
        """
        if isinstance(data, dict):
            if "name" not in data:
                data["name"] = str(uuid4())[0:8]
            # Generate namespaced ID for manifest template
            if "schedule_id" in data and "id" not in data:
                data["id"] = uuid5(
                    data["schedule_id"],
                    name=f"""NAME={data["name"]},KIND={data["kind"]},VERSION={data.get("version", 1)}""",
                )
        return data


class ManifestTemplate(ManifestTemplateBase, table=True):
    """Model used for database operations involving templates_v2 table rows"""

    model_config = {"validate_assignment": True}
    __tablename__: str = "templates_v2"  # type: ignore[misc]
    id: UUID5 = Field(primary_key=True)
    schedule_id: UUID4 = Field(foreign_key="schedules_v2.id", ondelete="CASCADE")

    def generate_id(self) -> UUID5:
        """An instance method for the ORM version of a ManifestTemplate for
        easy generation of a new ID, in case the name or version of the object
        changes.
        """
        self.id = uuid5(
            self.schedule_id,
            name=f"NAME={self.name},KIND={self.kind},VERSION={self.version}",
        )
        return self.id


class CreateManifestTemplate(ManifestTemplateBase):
    """A validating model for manifest templates in the schedule API."""

    # This model differs from its sibling in that the schedule_id is optional
    # rather than a mandatory FK constraint, allowing it to be used to
    # create new ManifestTemplate objects when a schedule and ID is applied
    # later
    id: UUID5 | None = None
    schedule_id: UUID4 | None = None
    manifest: Annotated[str, BeforeValidator(check_manifest_template_string)] = ""
