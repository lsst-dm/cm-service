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
    facility: Literal["USDF", "IN2P3", "LANC", "RAL"] = Field(
        default="USDF",
        title="Processing Facility Name",
        description="The name of the processing facility.",
        examples=["USDF", "IN2P3"],
    )
    include_files: list[str] = Field(
        default_factory=list,
        title="Facility-Specific BPS Include Files",
        description="A list of files to be added to the BPS submission as include files "
        "that are specific to the use of this Facility.",
        examples=[["${DRP_PIPE_DIR}/bps/caching/{instrument}/{site}/{caching}.yaml"]],
    )


class FacilityManifest(LibraryManifest[FacilitySpec]): ...
