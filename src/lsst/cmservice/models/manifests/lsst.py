"""Model library describing the runtime data model of a Library Manifest for an
LSST Stack, which aligns a nominal stack version with additional stack setup
instructions for a Campaign.
"""

from collections.abc import Mapping

from pydantic import Field

from . import LibraryManifest, ManifestSpec


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


class LsstManifest(LibraryManifest[LsstSpec]): ...
