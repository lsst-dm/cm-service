"""Model library describing the runtime data model of a Library Manifest for a
BPS operation.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from . import SPEC_CONFIG, LibraryManifest, ManifestSpec


class BpsSpec(ManifestSpec):
    """Configuration specification for a BPS Manifest. This is used primarily
    to fulfill a BPS submission file for a Group. These parameters may be set
    in a campaign-level BPS manifest or on the Step or Group under a `bps`
    mapping.
    """

    model_config = SPEC_CONFIG

    pipeline_yaml: (
        Annotated[
            str,
            Field(
                title="Pipeline YAML File",
                description="The absolute path to a Pipeline YAML specification file with optional anchor. "
                "The path must begin with a `/` or a `${...}` environment variable.",
                pattern="^(/|\\$\\{.*\\})(.*)(\\.yaml)(#.*)?$",
            ),
        ]
        | Annotated[
            None,
            Field(
                title="Null",
                description="A BPS Manifest does not need to specify a pipeline YAML file, but one is "
                "mandatory for a Step.",
            ),
        ]
    ) = Field(
        default=None,
        examples=[
            "${DRP_PIPE_DIR}/path/to/pipeline.yaml#anchor",
            "/absolute/path/to/file.yaml",
            "${CUSTOM_VAR}/file.yaml#anchor1,anchor2",
        ],
    )

    variables: (
        Annotated[
            dict[str, str],
            Field(
                title="BPS Variables",
                description="A mapping of name-value string pairs used to define additional top-level BPS "
                "settings or substitution variables. Note that the values are quoted in the output. For "
                "values that should not be quoted or otherwise used literally, see `literals`",
            ),
        ]
        | Annotated[
            None,
            Field(
                title="Null",
                description="This field is optional for a BPS configuration.",
            ),
        ]
    ) = Field(
        default=None,
        examples=[{"operator": "lsstsvc1"}],
    )

    include_files: (
        Annotated[
            list[str],
            Field(
                title="BPS Include Config Files",
                description="A list of include files added to the BPS submission file under the "
                "`includeConfigs` heading. This list is combined with `include_files` from other manifests.",
            ),
        ]
        | Annotated[
            None,
            Field(
                title="Null",
                description="This field is optional for a BPS configuration.",
            ),
        ]
    ) = Field(
        default=None,
        examples=[["${CTRL_BPS_DIR}/python/lsst/ctrl/bps/etc/bps_default.yaml"]],
    )

    literals: (
        Annotated[
            dict[str, Any],
            Field(
                title="BPS Configuration Literals",
                description="A mapping of arbitrary key-value sections to be added as additional literal "
                "YAML to the BPS submission file. For setting arbitrary BPS substitution variables, "
                "use `variables`.",
            ),
        ]
        | Annotated[
            None,
            Field(
                title="Null",
                description="This field is optional for a BPS configuration.",
            ),
        ]
    ) = Field(
        default=None,
        examples=[
            {
                "requestMemory": 2048,
                "numberOfRetries": 5,
                "retryUnlessExit": [1, 2],
                "finalJob": {"command1": "echo HELLO WORLD"},
            }
        ],
    )

    environment: (
        Annotated[
            dict[str, str],
            Field(
                title="BPS Environment Variables",
                description="A mapping of name-value string pairs used to defined additional values under "
                "the `environment` heading of the BPS submission file.",
                min_length=1,
            ),
        ]
        | Annotated[
            None,
            Field(
                title="Null",
                description="This field is optional for a BPS configuration.",
            ),
        ]
    ) = Field(
        default=None,
        examples=[{"LSST_S3_USE_THREADS": 1}],
    )

    payload: (
        Annotated[
            dict[str, str],
            Field(
                title="BPS Payload Configuration",
                description="A mapping of name-value string pairs used to define BPS payload options. "
                "Note that these values are generated from other configuration sources at runtime.",
            ),
        ]
        | Annotated[
            None,
            Field(
                title="Null",
                description="This field is optional for a BPS configuration.",
            ),
        ]
    ) = None

    extra_init_options: (
        Annotated[str, Field(description="Passthrough options added to the end of pipetaskinit")]
        | Annotated[
            None,
            Field(
                title="Null",
                description="This field is optional for a BPS configuration.",
            ),
        ]
    ) = None

    extra_qgraph_options: (
        Annotated[str, Field(description="Passthrough options for QuantumGraph builder.")]
        | Annotated[
            None,
            Field(
                title="Null",
                description="This field is optional for a BPS configuration.",
            ),
        ]
    ) = None

    extra_run_quantum_options: (
        Annotated[
            str, Field(description="Passthrough options for Quantum execution", examples=["--no-versions"])
        ]
        | Annotated[
            None,
            Field(
                title="Null",
                description="This field is optional for a BPS configuration.",
            ),
        ]
    ) = None

    extra_update_qgraph_options: (
        Annotated[str, Field(description="Passthrough options for QuantumGraph updater.")]
        | Annotated[
            None,
            Field(
                title="Null",
                description="This field is optional for a BPS configuration.",
            ),
        ]
    ) = None

    clustering: (
        Annotated[
            dict[str, Any],
            Field(
                title="BPS Clustering Configuration",
                description="A mapping of labeled clustering directives, added as literal YAML under the "
                "`cluster` heading. The top-level `clusterAlgorithm` should be added to `literals`.",
            ),
        ]
        | Annotated[
            None,
            Field(
                title="Null",
                description="This field is optional for a BPS configuration.",
            ),
        ]
    ) = Field(
        default=None,
        examples=[
            {
                "clusterLabel1": {
                    "dimensions": "detector",
                    "pipetasks": "isr,calibrateImage",
                    "partitionDimensions": "exposure",
                    "partititionMaxClusters": 10000,
                }
            }
        ],
    )

    operator: Annotated[
        str,
        Field(
            title="BPS Operator Name",
            description="The string name of a pilot or operator to reflect in the BPS configuration.",
        ),
    ] = "cmservice"


class BpsManifest(LibraryManifest[BpsSpec]): ...
