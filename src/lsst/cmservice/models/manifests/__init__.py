from pydantic import BaseModel, Field, AliasChoices

from ...common.enums import ManifestKind
from ...db.manifests_v2 import VersionedMetadata, ManifestSpec as ManifestSpec
from ...common.types import KindField


class LibraryManifest[SpecT](BaseModel):
    """A parameterized model for a Library Manifest, used to build a config-
    uration document for a particular kind of spec.
    """

    kind: KindField = Field(default=ManifestKind.other)
    metadata_: VersionedMetadata = Field(
        validation_alias=AliasChoices("metadata", "metadata_"),
        serialization_alias="metadata",
    )
    spec: SpecT = Field(
        validation_alias=AliasChoices("spec", "configuration", "data"),
        serialization_alias="spec",
    )
