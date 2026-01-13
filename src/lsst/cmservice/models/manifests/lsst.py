"""Model library describing the runtime data model of a Library Manifest for an
LSST Stack, which aligns a nominal stack version with additional stack setup
instructions for a Campaign.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import Field

from . import SPEC_CONFIG, LibraryManifest, ManifestSpec


class LsstSpec(ManifestSpec):
    """Spec model for an LSST Manifest."""

    model_config = SPEC_CONFIG
    lsst_version: str = Field(default="w_latest", description="LSST Stack version")
    lsst_distrib_dir: str = Field(description="Absolute path to a stack distribution location")
    prepend: str | None = Field(
        default=None,
        description="A newline-delimited string of shell actions to execute prior to stack setup.",
    )
    custom_lsst_setup: str | None = Field(
        default=None,
        description="A `\n`-delimited string of optional commands to be added to any Bash script that sets "
        "up the LSST Stack, to be executed verbatim *after* EUPS setup but *before* the payload command. "
        "Can be used to customize the Stack with EUPS, for example.",
    )
    append: str | None = Field(
        default=None,
        description="A newline-delimited string of shell actions to execute after the payload command.",
    )
    environment: Mapping = Field(
        default_factory=dict, description="A mapping of environment variables to set prior to stack setup"
    )
    ticket: str | None = Field(
        default=None,
        description="An optional JIRA ticket number associated with the campaign.",
    )
    description: str | None = Field(
        default=None,
        description="An optional description of the campaign.",
    )
    campaign: str | None = Field(default=None, description="An optional name for the campaign.")
    project: str | None = Field(
        default=None, description="An optional project name or identifier associated with the campaign."
    )


class LsstManifest(LibraryManifest[LsstSpec]): ...
