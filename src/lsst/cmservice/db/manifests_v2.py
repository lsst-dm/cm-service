"""Module for models representing generic CM Service manifests.

These manifests are used in APIs, especially when creating resources. They do
not necessarily represent the object's database or ORM model.
"""

from typing import Self

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationInfo, model_validator

from ..common.enums import DEFAULT_NAMESPACE, ManifestKind
from ..common.types import KindField


class Manifest[MetadataT, SpecT](BaseModel):
    """A parameterized model for an object's Manifest, used by APIs where the
    `spec` should be the kind's table model, more or less.
    """

    apiversion: str = Field(default="io.lsst.cmservice/v1")
    kind: KindField = Field(default=ManifestKind.other)
    metadata_: MetadataT = Field(
        validation_alias=AliasChoices("metadata", "metadata_"),
        serialization_alias="metadata",
    )
    spec: SpecT = Field(
        validation_alias=AliasChoices("spec", "configuration", "data"),
        serialization_alias="spec",
    )


class ManifestMetadata(BaseModel):
    """Generic metadata model for Manifests.

    Conventionally denormalized fields are excluded from the model_dump when
    serialized for ORM use.
    """

    name: str
    namespace: str


class ManifestSpec(BaseModel):
    """Generic spec model for Manifests.

    Notes
    -----
    Any spec body is allowed via config, but any fields that aren't first-class
    fields won't be subject to validation or available as model attributes
    except in the ``__pydantic_extra__`` dictionary. The full spec will be
    expressed via ``model_dump()``.
    """

    model_config = ConfigDict(extra="allow")


class VersionedMetadata(ManifestMetadata):
    """Metadata model for versioned Manifests."""

    version: int = 0


class ManifestModelMetadata(VersionedMetadata):
    """Manifest model for general Manifests. These manifests are versioned but
    a namespace is optional.
    """

    namespace: str = Field(default=str(DEFAULT_NAMESPACE))


class ManifestModel(Manifest[ManifestModelMetadata, ManifestSpec]):
    """Manifest model for generic Manifest handling."""

    @model_validator(mode="after")
    def custom_model_validator(self, info: ValidationInfo) -> Self:
        """Validate an Campaign Manifest after a model has been created."""
        if self.kind in [ManifestKind.campaign, ManifestKind.node, ManifestKind.edge]:
            raise ValueError(f"Manifests may not be a {self.kind.name} kind.")

        return self


class CampaignMetadata(BaseModel):
    """Metadata model for a Campaign Manifest.

    Campaign metadata does not require a namespace field.
    """

    name: str


class CampaignManifest(Manifest[CampaignMetadata, ManifestSpec]):
    """validating model for campaigns"""

    @model_validator(mode="after")
    def custom_model_validator(self, info: ValidationInfo) -> Self:
        """Validate an Campaign Manifest after a model has been created."""
        if self.kind is not ManifestKind.campaign:
            raise ValueError("Campaigns may only be created from a <campaign> manifest")

        return self
