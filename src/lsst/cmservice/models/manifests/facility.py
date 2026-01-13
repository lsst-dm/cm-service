"""Model library describing the runtime data model of a Library Manifest for a
processing site or facility.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from . import SPEC_CONFIG, LibraryManifest, ManifestSpec


class FacilitySpec(ManifestSpec):
    model_config = SPEC_CONFIG
    facility: Literal["USDF", "IN2P3", "LANC", "RAL"] = Field(
        default="USDF",
        description="The name of the processing facility.",
    )


class FacilityManifest(LibraryManifest[FacilitySpec]): ...
