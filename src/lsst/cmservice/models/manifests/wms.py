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
    """Configuration specification for a WMS Manifest. These settings are used
    to define behaviors of "launch" jobs as well as configuring relevant
    sections of a BPS Submission file, especially those values concerned with
    batch-system specific items.

    Resource management settings set here are specific to the launch
    environment. Resource management for BPS submissions should be set in the
    BPS manifest instead (see `bps.literals`, e.g.).
    """

    model_config = SPEC_CONFIG

    batch_system: Annotated[
        Literal["htcondor", "panda"],
        Field(
            title="WMS Batch System",
            validation_alias=AliasChoices("batch_system", "wms"),
            description="The well-known name of the batch technology.",
        ),
    ] = Field(
        default="htcondor",
        examples=["htcondor", "panda"],
    )

    include_files: Annotated[
        list[str],
        Field(
            title="BPS Include Files",
            description="A list of BPS include files, if any, specific to this WMS.",
        ),
    ] = Field(default_factory=list, examples=[["${EUPS_PRODUCT_DIR}/wms/include_me.yaml"]])

    environment: Annotated[
        Mapping,
        Field(
            default_factory=dict,
            title="Environment Mapping",
            description="A mapping of environment variables to set prior to bps submit.",
        ),
    ] = Field(
        default_factory=dict,
        examples=[{"environment": {"_CONDOR_SCHEDD_HOST": "myfavoritehost"}}],
    )

    service_class: Annotated[
        str,
        Field(
            title="Service Class Name",
            description="wmsServiceClass used by the batch system",
        ),
    ] = Field(
        default="lsst.ctrl.bps.htcondor.HTCondorService",
        examples=["lsst.ctrl.bps.htcondor.HTCondorService"],
    )

    request_cpus: Annotated[
        int, Field(description="The number of CPUs requested of the WMS for a Launch Task")
    ] = Field(
        default=1,
    )

    request_mem: (
        Annotated[
            str,
            Field(
                title="Launch Task Memory Request",
                description="The amount of memory requested of the WMS for a Launch Task",
            ),
        ]
        | Annotated[None, Field(title="Null", description="This field is optional for a WMS configuration.")]
    ) = Field(default=None, examples=["1024k"])

    request_disk: (
        Annotated[
            str,
            Field(
                title="Lauch Task Disk Request",
                description="The amount of disk space requested of the WMS for a Launch Task",
            ),
        ]
        | Annotated[None, Field(title="Null", description="This field is optional for a WMS configuration.")]
    ) = Field(default=None, examples=["10240k"])

    batch_name: (
        Annotated[
            str,
            Field(title="Batch Name", description="An optional name to associate with jobs sent to the WMS"),
        ]
        | Annotated[None, Field(title="Null", description="This field is optional for a WMS configuration.")]
    ) = Field(default=None, examples=["cmservice-usdf-prod", "cmservice-usdf-dev"])


class WmsManifest(LibraryManifest[WmsSpec]): ...
