"""Module for models representing generic CM Service manifests.

These manifests are used in APIs, especially when creating resources. They do
not necessarily represent the object's database or ORM model.
"""

from collections.abc import Mapping, MutableSequence, Sequence
from typing import Annotated, Literal, Self
from uuid import UUID, uuid4

from pydantic import (
    UUID5,
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    ValidationInfo,
    model_validator,
)

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


class LibraryManifest[SpecT](BaseModel):
    """A parameterized model for Library Manifest, used by APIs where the
    `spec` should be the kind's table model, more or less.
    """

    kind: KindField = Field(default=ManifestKind.other)
    metadata_: "VersionedMetadata" = Field(
        validation_alias=AliasChoices("metadata", "metadata_"),
        serialization_alias="metadata",
    )
    spec: SpecT = Field(
        validation_alias=AliasChoices("spec", "configuration", "data"),
        serialization_alias="spec",
    )


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
    version: int = Field(default=0, description="Version of the Manifest", exclude=True)


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
    """Manifest model for generic Manifest handling."""

    @model_validator(mode="after")
    def custom_model_validator(self, info: ValidationInfo) -> Self:
        """Validate an Campaign Manifest after a model has been created."""
        if self.kind in [ManifestKind.campaign, ManifestKind.node, ManifestKind.edge]:
            raise ValueError(f"Manifests may not be a {self.kind.name} kind.")

        return self


class CampaignManifest(Manifest[ManifestModelMetadata, ManifestSpec]):
    """validating model for campaigns"""

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
    crtime: int = Field(default_factory=element_time)


class EdgeSpec(ManifestSpec):
    """Spec model for an Edge Manifest."""

    source: str = Field(exclude=True)
    target: str = Field(exclude=True)


class EdgeManifest(Manifest[EdgeMetadata, EdgeSpec]):
    """validating model for Edges"""

    @model_validator(mode="after")
    def custom_model_validator(self, info: ValidationInfo) -> Self:
        """Validate an Edge Manifest after a model has been created."""
        if self.kind is not ManifestKind.edge:
            raise ValueError("Edges may only be created from an <edge> manifest")

        return self


class NodeMetadata(ManifestMetadata):
    """Metadata model for a Node Manifest.

    Nodes may specify their specific kind via metadata, which defaults to
    "other". Note this is different to the kind of the Manifest, which for a
    Node is always "node".
    """

    kind: KindField = Field(default=ManifestKind.other, exclude=True)


class NodeManifest(Manifest[NodeMetadata, ManifestSpec]):
    """validating model for Nodes"""

    @model_validator(mode="after")
    def custom_model_validator(self, info: ValidationInfo) -> Self:
        """Validate a Node Manifest after a model has been created."""
        if self.kind is not ManifestKind.node:
            raise ValueError("Nodes may only be created from an <node> manifest")

        return self


class ButlerCollectionsSpec(BaseModel):
    """Specification for the definition of Butler collections used throughout
    a campaign.
    """

    campaign_input: list[str] = Field(description="The campaign source collection")
    ancillary: list[str] = Field(default_factory=list)
    out: str = Field(
        description="The public output collection for this Campaign.",
        default_factory=lambda: uuid4().__str__(),
        alias="campaign_public_output",
    )
    campaign_output: str | None = Field(
        default=None, description="The private output collection for a campaign; {out}/output"
    )
    step_input: str | None = Field(default=None, description="{out}/{step}/input")
    step_output: str | None = Field(default=None, description="{out}/{step}_output")
    step_public_output: str | None = Field(default=None, description="{out}/{step}")
    group_output: str | None = Field(default=None, description="{out}/{step}/{group}")
    run: str | None = Field(
        default=None,
        description="The run collection affected by a Node's execution; {out}/{step}/{group}/{job}",
        alias="job_run",
    )


class ButlerSpec(ManifestSpec):
    """Spec model for a Butler Manifest."""

    repo: str = Field(description="Name of a Butler known to the application's Butler Factory.")
    predicates: Sequence[str] = Field(default_factory=list)
    collections: ButlerCollectionsSpec


class LsstSpec(ManifestSpec):
    """Spec model for an LSST Manifest."""

    lsst_version: str = Field(default="w_latest", description="LSST Stack version")
    lsst_distrib_dir: str = Field(description="Absolute path to a stack distribution location")
    prepend: str | None = Field(
        default=None,
        description="A newline-delimited string of shell actions to execute prior to stack setup.",
    )
    append: str | None = Field(
        default=None,
        description="A newline-delimited string of shell actions to execute after to stack setup.",
    )
    environment: Mapping = Field(
        default_factory=dict, description="A mapping of environment variables to set prior to stack setup"
    )


class GroupedStepGroupSpec(ManifestSpec):
    split_by: Literal["values", "query"]
    values: Sequence[str | int | Sequence[str | int] | Mapping]
    field: str
    dataset: str
    min_groups: int
    max_size: int


class GroupedStepSpec(ManifestSpec):
    """Spec model for a Node of kind GroupedStep."""

    predicates: Annotated[
        MutableSequence[str], PlainSerializer(lambda x: " AND ".join(x), return_type=str)
    ] = Field(serialization_alias="data_query")
    groups: GroupedStepGroupSpec | None
    pipeline_yaml: str


class ButlerManifest(LibraryManifest[ButlerSpec]): ...


class LsstManifest(LibraryManifest[LsstSpec]): ...
