"""ORM Models for v2 notification events and labels."""

from sqlmodel import Column, Enum, Field, LargeBinary

from ..enums import NotificationLabelEnum
from ..types import NotificationLabelKindField
from .base import BaseSQLModel
from .campaigns import jsonb_column


class NotificationLabelBase(BaseSQLModel):
    """notification_labels_v2 base model, used as a notifications queue"""

    name: str = Field(description="Label name", primary_key=True)
    kind: NotificationLabelKindField = Field(
        description=(
            "The kind of notification backend used by the label, such as a webhook or API. "
            "Every kind of notification label must match an implementation of the same kind."
        ),
        sa_column=Column(
            "kind", Enum(NotificationLabelEnum, length=20, native_enum=False, create_constraint=False)
        ),
    )
    configuration: dict = jsonb_column("configuration", aliases=["configuration", "data", "spec"])
    secret: bytes = Field(
        description=(
            "An encrypted secret associated with the label and meaningful to the kind's implementation, "
            "such as an API key or webhook url. The secret must be encrypted with a key "
            "known to the application. This secret must be a urlsafe base64 encoded string."
        ),
        sa_column=Column("secret", LargeBinary),
    )


class NotificationLabel(NotificationLabelBase, table=True):
    """Model used for db ops involving notification_labels_v2 table rows"""

    model_config = {"validate_assignment": True}

    __tablename__: str = "notification_labels_v2"  # type: ignore[misc]
