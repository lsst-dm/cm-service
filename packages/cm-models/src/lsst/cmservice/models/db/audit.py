"""Module for database and object models for Audit Logs."""

from uuid import UUID

from pydantic import AwareDatetime
from pydantic_extra_types.uuid_types import UUID7, uuid7
from sqlmodel import Column, DateTime, Enum, Field

from ..enums import AuditActionEnum, ManifestKind
from ..lib.timestamp import now_utc
from ..types import ActionField, KindField
from .base import BaseSQLModel
from .campaigns import jsonb_column


class AuditLogBase(BaseSQLModel):
    """audit_log_v2 base model, used to create new audit log objects."""

    id: UUID7 = Field(default_factory=uuid7, primary_key=True)
    created_at: AwareDatetime = Field(
        description="The `datetime` (UTC) at which this audit log entry was created",
        default_factory=now_utc,
        sa_column=Column(DateTime(timezone=True)),
    )
    actor: str = Field(description="The user or system that performed the action")
    action: ActionField = Field(
        description="The action performed",
        sa_column=Column(
            "action", Enum(AuditActionEnum, length=20, native_enum=False, create_constraint=False)
        ),
    )
    request_id: UUID = Field(description="The request ID associated with the action")
    object_id: UUID = Field(description="The ID of the object that was acted upon")
    object_type: KindField = Field(
        description="The type of the object that was acted upon",
        sa_column=Column(
            "object_type", Enum(ManifestKind, length=20, native_enum=False, create_constraint=False)
        ),
    )
    object_name: str = Field(description="The name of the object that was acted upon")
    context: dict = jsonb_column("context", aliases=["context", "fields"])


class AuditLog(AuditLogBase, table=True):
    """Model used for database operations involving audit_log_v2 table rows"""

    model_config = {"validate_assignment": True}

    __tablename__: str = "audit_log_v2"  # type: ignore[misc]
