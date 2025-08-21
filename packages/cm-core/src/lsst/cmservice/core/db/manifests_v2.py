"""Module for models representing generic CM Service manifests.

These manifests are generally used in APIs, especially when creating resources.
They do not necessarily represent the object's database or ORM model.
"""

from typing import Self
from uuid import UUID, uuid4

from pydantic import UUID5, AliasChoices, BaseModel, ConfigDict, Field, ValidationInfo, model_validator

from ..common.enums import DEFAULT_NAMESPACE, ManifestKind
from ..common.timestamp import element_time
from ..common.types import KindField


class ManifestRequest(BaseModel):
    """Request Model for routes requesting manifests."""

    campaign_id: UUID5 = Field(DEFAULT_NAMESPACE, description="The campaign namespace for the manifest")
    id: UUID5 | None = Field(None, description="A manifest ID")
    kind: KindField | UUID5 | None = Field(..., description="The kind of manifest")
    name: str | None = Field(None, description="The name of a manifest")
    version: int | None = Field(None, description="The version of the manifest")

    @model_validator(mode="after")
    def custom_model_validator(self, info: ValidationInfo) -> Self:
        """Validate an Campaign Manifest after a model has been created."""
        if isinstance(self.kind, UUID):
            self.id = self.kind
            self.kind = None

        return self


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


class VersionedMetadata(BaseModel):
    """Metadata model for versioned Manifests with timestamps."""

    version: int = Field(exclude=True, default=0)
    crtime: int = Field(default_factory=element_time)
    mtime: int | None = Field(default=None)


class ManifestMetadata(VersionedMetadata):
    """Generic metadata model for Manifests.

    Conventionally denormalized fields are excluded from the model_dump when
    serialized for ORM use.
    """

    name: str = Field(exclude=True)
    namespace: str = Field(exclude=True)


class ManifestModelMetadata(ManifestMetadata):
    """Manifest model for general Manifests. These manifests are versioned but
    a namespace is optional (defaultable).
    """

    namespace: str = Field(default=str(DEFAULT_NAMESPACE), exclude=True)


class ManifestModel(Manifest[ManifestModelMetadata, ManifestSpec]):
    """Validating model for handling generic Manifests in an API where the
    manifest may not be a Campaign, Node, or Edge kind. Instead, this model is
    used to validate "Library" manifests added to the "manifests" table.
    """

    @model_validator(mode="after")
    def custom_model_validator(self, info: ValidationInfo) -> Self:
        """Validate an Campaign Manifest after a model has been created."""
        if self.kind in [ManifestKind.campaign, ManifestKind.node, ManifestKind.edge]:
            raise ValueError(f"Manifests may not be a {self.kind.name} kind.")

        return self


class CampaignManifest(Manifest[ManifestModelMetadata, ManifestSpec]):
    """Validating model for a Campaign Manifest"""

    @model_validator(mode="after")
    def custom_model_validator(self, info: ValidationInfo) -> Self:
        """Validate an Campaign Manifest after a model has been created."""
        if self.kind is not ManifestKind.campaign:
            raise ValueError("Campaigns may only be created from a <campaign> manifest")

        return self


class EdgeMetadata(ManifestMetadata):
    """Metadata model for an Edge Manifest.

    A default random alphanumeric 8-byte name is generated if no name provided.
    """

    name: str = Field(default_factory=lambda: uuid4().hex[:8], exclude=True)


class EdgeSpec(ManifestSpec):
    """Configuration Spec model for an Edge Manifest."""

    source: str = Field(exclude=True)
    target: str = Field(exclude=True)


class EdgeManifest(Manifest[EdgeMetadata, EdgeSpec]):
    """Validating model for Edge Manifests, used by an API."""

    @model_validator(mode="after")
    def custom_model_validator(self, info: ValidationInfo) -> Self:
        """Validate an Edge Manifest after a model has been created."""
        if self.kind is not ManifestKind.edge:
            raise ValueError("Edges may only be created from an <edge> manifest")

        return self


class NodeMetadata(ManifestMetadata):
    """Metadata model for a campaign graph Node.

    Nodes may specify their specific kind via metadata, which defaults to
    "other". Note this is different to the kind of the Manifest, which for a
    Node is always "node".
    """

    kind: KindField = Field(default=ManifestKind.other, exclude=True)


class NodeManifest(Manifest[NodeMetadata, ManifestSpec]):
    """validating model for Node Manifests, used by an API."""

    @model_validator(mode="after")
    def custom_model_validator(self, info: ValidationInfo) -> Self:
        """Validate a Node Manifest after a model has been created."""
        if self.kind is not ManifestKind.node:
            raise ValueError("Nodes may only be created from an <node> manifest")

        return self
