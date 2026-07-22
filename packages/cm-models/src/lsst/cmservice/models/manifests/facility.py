"""Model library describing the runtime data model of a Library Manifest for a
processing site or facility.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from . import SPEC_CONFIG, LibraryManifest, ManifestSpec


# FIXME determine whether to rename this to Site* or to rename facility* for
# consistency
class FacilitySpec(ManifestSpec):
    model_config = SPEC_CONFIG | {"title": "site_spec"}
    facility: Literal["SLAC", "IN2P3", "LANCS", "RAL"] = Field(
        default="SLAC",
        title="Processing Facility Name",
        description="Name of the processing facility, equivalent to the BPS `computeSite` setting",
        examples=["SLAC", "IN2P3"],
    )
    literals: dict | None = Field(
        default=None,
        title="Processing Facility Literal Configuration, used as top-level BPS configuration",
        examples=[{"site": {"SLAC": {"profile": {"condor": {"+Walltime": 43200}}}}}],
    )
    include_files: list[str] = Field(
        default_factory=list,
        title="Facility-Specific BPS Include Files",
        description="List of files to be added to the BPS submission as include files "
        "that are specific to the use of this Facility.",
        examples=[["${DRP_PIPE_DIR}/bps/caching/{instrument}/{site}/{caching}.yaml"]],
    )
    provisioned_platform: str = Field(
        default="s3df",
        title="Provisioning Platform Name",
        description="Name of the provisioning platform at the facility, for use with `allocateNodes.py`",
        examples=["s3df"],
    )
    provisioned_queue: str = Field(
        default="milano",
        title="Provisioning Queue",
        description="Name of the provisioning queue or partition for provisioned glidein",
        examples=["milano", "roma"],
    )

    provisioned_account_group: str = Field(
        default="rubin:developers",
        title="Accounting User",
        description="Name of the accounting user or group associated with the provisioned glidein",
        examples=["rubin:developers", "rubin:production"],
    )


class FacilityManifest(LibraryManifest[FacilitySpec]): ...
