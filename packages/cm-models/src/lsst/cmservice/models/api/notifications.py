"""Module for API models related to the Notifications interface.

This module includes API request and response models that are not otherwise
part of the ORM database model hierarchy.
"""

from typing import Annotated

from pydantic import AliasChoices, BaseModel, Field

from ..enums import NotificationLabelEnum
from ..types import NotificationLabelKindField
from .manifests import Manifest, ManifestSpec


class NotificationLabelConfiguration(ManifestSpec):
    """Model representing the configuration details of a Notification label."""

    secret_plaintext: Annotated[
        bytes,
        Field(
            description="The plaintext value of the secret associated with this label "
            "and relevant to the label kind. This value will be encrypted server-side "
            "before any serialization to durable storage.",
            validation_alias=AliasChoices("secret", "secret_plaintext", "plaintext"),
            serialization_alias="secret_plaintext",
        ),
    ]
    filters: Annotated[
        list,
        Field(
            default_factory=list,
            description="A list of three-tuples of `kind:from:to` filter identifiers "
            "for this notification label. If not provided, a default filter will "
            "be applied.",
        ),
    ]


class NotificationLabelMetadata(BaseModel):
    """A metadata model for Notification Label manifests"""

    name: Annotated[str, Field(description="The unique name of this notification label")]
    kind: NotificationLabelKindField = Field(default=NotificationLabelEnum.slack)


class NotificationLabelManifest(Manifest[NotificationLabelMetadata, NotificationLabelConfiguration]):
    """A Manifest for a Notification Label consistent with the design of other
    campaign element API objects.
    """

    ...
