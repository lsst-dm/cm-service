from pydantic import AliasChoices, BaseModel, Field

from ...common.enums import ManifestKind
from ...common.types import KindField
from ...db.manifests_v2 import ManifestSpec as ManifestSpec
from ...db.manifests_v2 import VersionedMetadata


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
