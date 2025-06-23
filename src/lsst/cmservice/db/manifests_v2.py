"""Module for models representing generic CM Service manifests."""

from pydantic import AliasChoices
from sqlmodel import Field, SQLModel

from ..common.enums import ManifestKind
from ..common.types import KindField


class ManifestWrapper(SQLModel):
    """A model for an object's Manifest wrapper, used by APIs where the `spec`
    should be the kind's table model, more or less.
    """

    apiversion: str = Field(default="io.lsst.cmservice/v1")
    kind: KindField = Field(default=ManifestKind.other)
    metadata_: dict = Field(
        default_factory=dict,
        schema_extra={
            "validation_alias": AliasChoices("metadata", "metadata_"),
            "serialization_alias": "metadata",
        },
    )
    spec: dict = Field(
        default_factory=dict,
        schema_extra={
            "validation_alias": AliasChoices("spec", "configuration", "data"),
            "serialization_alias": "spec",
        },
    )
