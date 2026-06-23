"""Model library describing the runtime data model of a Library Manifest for an
LSST Stack, which aligns a nominal stack version with additional stack setup
instructions for a Campaign.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated

from pydantic import BeforeValidator, Field

from ..lib.parsers import strip_trailing_slash
from . import SPEC_CONFIG, LibraryManifest, ManifestSpec


class LsstSpec(ManifestSpec):
    """Spec model for an LSST Manifest."""

    model_config = SPEC_CONFIG

    artifact_path: (
        Annotated[
            str,
            Field(
                title="Artifact Path",
                examples=["/path/to/writable/shared/location"],
            ),
        ]
        | Annotated[
            None,
            Field(
                title="Null",
                examples=[None],
            ),
        ]
    ) = Field(
        default=None,
        exclude=True,
        description="The path to a writable shared location where the service "
        "will create artifacts for the campaign. This is a read-only field that "
        "should only be set in a library manifest.",
    )

    lsst_version: str = Field(
        default="w_latest",
        title="Stack Version",
        description="LSST Stack version or tag",
        examples=["w_latest", "d_latest", "w_2026_01"],
    )
    lsst_distrib_dir: Annotated[
        str,
        BeforeValidator(strip_trailing_slash),
        Field(
            title="LSST Distribution Directory",
            description="Absolute path to a stack distribution location. Should not have a trailing slash.",
            examples=["/sdf/group/rubin/sw/tag/<tag>", "/cvmfs/sw.lsst.eu/linux-x86_64/lsst_distrib/<tag>"],
        ),
    ]
    prepend: list[str | tuple[str, ...]] | None = Field(
        default=None,
        title="Stack Setup Prepend Commands",
        description="A list of shell actions to execute prior to stack setup.",
        examples=[
            [("echo", "-e", "Starting New Campaign")],
            ["echo Hello World"],
        ],
    )
    custom_lsst_setup: list[str | tuple[str, ...]] | None = Field(
        default=None,
        title="Custom Stack Setup Commands",
        description="A list of script commands (or a tuple of command tokens) representing optional commands"
        "to be added to any Bash script that sets up the LSST Stack, to be executed verbatim *after* EUPS "
        "setup but *before* the payload command. Can be used to customize the Stack with EUPS, for example.",
        examples=[
            [("setup", "--just", "--root=/path/to/custom/product")],
            ["setup --just --root=/path/to/custom/product"],
        ],
    )
    custom_group_payload: list[str | tuple[str, ...]] = Field(
        default_factory=list,
        title="Custom Group Payload Commands",
        description="A list of script commands (or a tuple of command tokens) representing optional commands "
        "to be added to any Bash script that executes a payload for a Group. These commands will not be "
        "added to any launcher script for any Node other than groups.",
        examples=[
            [("python", "-m", "lsst.package.module.submodule")],
            ["mc cp bucket/path/to/some/object ."],
        ],
    )
    custom_payload: list[str | tuple[str, ...]] = Field(
        default_factory=list,
        title="Custom Payload Commands",
        description="A list of script commands (or a tuple of command tokens) representing optional commands "
        "to be added to any Bash script that executes a payload.",
        examples=[
            [("python", "-m", "lsst.package.module.submodule")],
        ],
    )
    append: list[str | tuple[str, ...]] | None = Field(
        default=None,
        title="Launcher Script Afterburner Commands",
        description="A list of shell actions to execute after the payload command.",
        examples=[
            [("source", "/path/to/custom/script.sh")],
            ["echo Finished"],
        ],
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
