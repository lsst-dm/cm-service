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
    lsst_version: str = Field(
        default="w_latest",
        title="Stack Version",
        description="LSST Stack version or tag",
        examples=["w_latest", "d_latest", "w_2026_01"],
    )
    lsst_distrib_dir: str = Field(
        title="LSST Distribution Directory",
        description="Absolute path to a stack distribution location",
        examples=["/sdf/group/rubin/sw/tag/<tag>", "/cvmfs/sw.lsst.eu/linux-x86_64/lsst_distrib/<tag>/"],
    )
    prepend: str | None = Field(
        default=None,
        title="Stack Setup Prepend Commands",
        description="A newline-delimited string of shell actions to execute prior to stack setup.",
        examples=["echo Hello World", "echo Starting New Campaign\necho Hello World"],
    )
    custom_lsst_setup: str | None = Field(
        default=None,
        title="Custom Stack Setup Commands",
        description="A newline-delimited string of optional commands to be added to any Bash script that "
        "sets up the LSST Stack, to be executed verbatim *after* EUPS setup but *before* the payload "
        "command. Can be used to customize the Stack with EUPS, for example.",
        examples=["setup --just --root=/path/to/custom/product"],
    )
    append: str | None = Field(
        default=None,
        title="Stack Setup Append Commands",
        description="A newline-delimited string of shell actions to execute after the payload command.",
        examples=["echo Finished", "source /path/to/custom/script.sh"],
    )
    environment: Mapping | None = Field(
        default_factory=dict,
        title="Stack Setup Environment Variables",
        description="A mapping of environment variables to set prior to stack setup",
        min_length=1,
        examples=[{"environment": {"LSST_USE_OPTIONAL_FEATURE": 1}}],
    )
    ticket: str | None = Field(
        default=None,
        title="Ticket Number",
        description="An optional JIRA ticket number associated with the campaign.",
        examples=[{"ticket": "DM-XXXXX"}],
    )
    description: str | None = Field(
        default=None,
        title="Campaign Description",
        description="An optional description of the campaign.",
        examples=["An optional description of the campaign."],
    )
    campaign: str | None = Field(
        default=None,
        title="Campaign Name",
        description="An optional name for the campaign.",
        examples=["CustomCampaign"],
    )
    project: str | None = Field(
        default=None,
        title="Campaign Project or Epic",
        description="An optional project name or identifier associated with the campaign.",
        examples=["My special campaign", "Daily batch processing"],
    )


class LsstManifest(LibraryManifest[LsstSpec]): ...
