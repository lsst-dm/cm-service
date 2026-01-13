"""Model library describing the runtime data model of a Library Manifest for a
Work Management or Batch system used by a Campaign for compute resources.

Configuration provided by a WMS manifest generally align with the WMS config-
uration block of a BPS submit file.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import AliasChoices, Field

from . import SPEC_CONFIG, LibraryManifest, ManifestSpec


class WmsSpec(ManifestSpec):
    model_config = SPEC_CONFIG
    batch_system: Annotated[
        Literal["htcondor", "panda"],
        Field(
            validation_alias=AliasChoices("batch_system", "wms"),
            description="The well-known name of the batch technology.",
        ),
    ] = "htcondor"
    include_files: list[str] = Field(
        default_factory=list, description="A list of BPS include files, if any, specific to this WMS."
    )
    environment: Mapping = Field(
        default_factory=dict, description="A mapping of environment variables to set prior to bps submit."
    )
    service_class: Annotated[
        str,
        Field(description="wmsServiceClass used by the batch system"),
    ] = "lsst.ctrl.bps.htcondor.HTCondorService"
    request_cpus: Annotated[
        int, Field(description="The number of CPUs requested of the WMS for a Launch Task")
    ] = 1
    request_mem: (
        Annotated[str, Field(description="The amount of memory requested of the WMS for a Launch Task")]
        | None
    ) = None
    request_disk: (
        Annotated[str, Field(description="The amount of disk space requested of the WMS for a Launch Task")]
        | None
    ) = None
    batch_name: (
        Annotated[str, Field(description="An optional name to associate with jobs sent to the WMS")] | None
    ) = None


class WmsManifest(LibraryManifest[WmsSpec]): ...
