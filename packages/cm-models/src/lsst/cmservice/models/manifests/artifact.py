"""Model for an Artifact manifest."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from . import SPEC_CONFIG, LibraryManifest, ManifestSpec


class ArtifactSpec(ManifestSpec):
    """Configuration specification for an Artifact Manifest."""

    model_config = SPEC_CONFIG

    artifacts: Annotated[
        dict[str, str],
        Field(
            description="A mapping of static artifact payloads where the key is the file name and the value "
            "is the template source of the artifact. These template sources are rendered at the same time "
            "as other node templates.",
            examples=[{"filename.txt": "file contents\n"}],
        ),
    ] = Field(default_factory=dict)

    resources: Annotated[
        dict[str, str],
        Field(
            description="A mapping of resources where the key is the target file name of the resource "
            "(relative to the current node's artifact path) and the value is a `ResourcePath` expression "
            "usually of an `s3://{profile}@{bucket}/{key}` form.",
            examples=[{"local_file.txt": "s3://embargo@bucket/path/to/remote_file.txt"}],
        ),
    ] = Field(default_factory=dict)


class ArtifactManifest(LibraryManifest[ArtifactSpec]): ...
