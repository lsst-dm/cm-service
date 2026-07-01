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

    custom_setup: list[str | tuple[str, ...]] | None = Field(
        default=None,
        title="Custom WMS Setup Commands",
        description="A list of script commands (or a tuple of command tokens) representing optional commands"
        "to be added to any Bash script that sets up the LSST Stack, to be executed verbatim *after* LSST "
        "setup but *before* the payload command. Used to customize the launch context for a specific WMS",
        examples=[
            [("setup", "--just", "--root=/path/to/custom/product")],
            ["setup --just --root=/path/to/custom/product"],
        ],
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
    ] = Field(default=1)

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
            Field(
                title="Nodeset Name",
                description="Batch or Nodeset name for matching jobs with provisioned glideins. "
                "If auto provisioning is enabled, this must not be null.",
            ),
        ]
        | Annotated[None, Field(title="Null", description="This field is optional for a WMS configuration.")]
    ) = Field(default=None, examples=["cmservice-usdf-prod", "cmservice-usdf-dev"])

    auto_provision: Annotated[
        bool,
        Field(
            title="Automatic Provisioning",
            description="Whether automatic provisioning of resources is enabled for the WMS",
        ),
    ] = Field(default=False)

    provisioned_node_count: Annotated[
        int,
        Field(
            title="Provisioned Node Count",
            description="Node count requested for automatic provisioning, e.g., glidein size",
        ),
    ] = Field(default=10, examples=[10, 100])

    provisioned_max_wall_time: Annotated[
        str,
        Field(
            title="Maximum Wall Clock Time",
            description="Maximum lifetime for provisioned glidein, as time-component format [days-HH:MM:SS]",
        ),
    ] = Field(default="0-1:00:00", examples=["3600", "10:00:00", "6-00:00:00"])

    provisioned_idle_time: Annotated[
        int,
        Field(
            title="Maximum Idle Time",
            description="Maximum idle time for provisioned glidein, in seconds",
        ),
    ] = Field(default=900, examples=[600, 900, 86400])

    provisioned_extra_arguments: Annotated[
        list[str],
        Field(
            title="Extra arguments for auto provisioning",
            description="A list of string arguments to be included as extra arguments to auto provisioning, "
            "e.g., `allocateNodes.py`",
        ),
    ] = Field(
        default_factory=list, examples=[["--pack", "--exclusive-user"], ["--exclude", "badnode1", "badnode2"]]
    )

    provisioned_check_interval: Annotated[
        int,
        Field(
            title="Provisioning Check Interval",
            description="Time between auto provision (`allocateNodes.py`) checks in seconds.",
        ),
    ] = Field(default=600, examples=[30, 600, 900, 3600])


class WmsManifest(LibraryManifest[WmsSpec]): ...
