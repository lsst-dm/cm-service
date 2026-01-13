"""Models for Step Configuration.

During runtime, the Step Configuration is not necessarily validated against
these models, but the generated JSON Schema may be used to validate step
configuration inputs. These models are considered the source of truth for a
step's configuration.
"""

from __future__ import annotations

from collections.abc import MutableSequence, Sequence
from typing import Annotated, Literal

from pydantic import Field, PlainSerializer

from . import SPEC_CONFIG, LibraryManifest, ManifestSpec, SubfieldManifest
from .bps import BpsSpec
from .butler import ButlerSpec
from .facility import FacilitySpec
from .lsst import LsstSpec
from .wms import WmsSpec


class StepGroupsQuerySpec(ManifestSpec):
    """Configuration for a Butler Query-based Grouping, where the results of
    a Butler Query is used to create groups based on a target number of or
    maximum size for each group. The data IDs returned from the query are
    partitioned according to the `min_groups` and/or `max_size` settings as
    appropriate. The Butler used for this query is the Butler defined for the
    step or the campaign.
    """

    model_config = SPEC_CONFIG | {"title": "Split by Query"}
    split_by: Literal["query"]
    dataset: str = Field(description="The name of a dataset to query")
    dimension: str = Field(
        description="The name of a Butler dimension to associate with each "
        "grouping `value` to form a query predicate.",
        examples=["tract", "raw"],
    )
    field: str | None = Field(default=None, description="TBD")
    min_groups: int = Field(
        default=1,
        description="The minimum number of groups created to fit all elements, "
        "as long as there is at least 1 member",
    )
    max_size: int = Field(
        default=1_000_000,
        description="The maximum number of elements to fit into a single group, "
        "irrespective of other concerns",
    )


class StepGroupsValueRange(ManifestSpec):
    """Configuration for a dimension value range to use to define a single
    group in a Step.
    """

    model_config = SPEC_CONFIG | {"title": "Value Range"}
    min: int = Field(description="Minimum dimension value for a range")
    max: int = Field(description="Maximum dimension value for a range")
    endpoint: bool = Field(
        default=True,
        description="Whether the range is right-open or right-closed",
    )


class StepGroupsValuesSpec(ManifestSpec):
    """Step Group Configuration using a Values-based Splitter. Each Step will
    spawn one group for each specified value, list of values, or value range.
    """

    model_config = SPEC_CONFIG | {"title": "Split by Value"}
    split_by: Literal["values"]
    values: Sequence[str | int | Sequence[int] | StepGroupsValueRange] = Field(
        description="A list of values, each one of which represents the data IDs used for a single group. If "
        "the sequence item is a scalar, then the group will consist of only that singular data ID "
        "(e.g. `dimension={value}`) but if the sequence item is a list or a range definition, then the data "
        "query for the group will use different operators with the item, e.g., "
        "`dimension IN (...)` or `dimension >= {min} AND < {max}. When the `endpoint` of a value range is "
        "included (`True`) then the `<= {max}` operator is used instead.",
        examples=[["value", 1, 2, 3, [4, 5, 6], {"min": 100, "max": 199, "endpoint": True}]],
    )
    dimension: str = Field(
        description="The name of a Butler dimension to associate with each grouping `value` to form a "
        "query predicate.",
        examples=["tract", "visit"],
    )


class StepSpec(ManifestSpec):
    """Configuration model for a Step Node.

    A Step Node may be broken into more than 1 group using the `groups`
    configuration. A Step Node may also override any Manifest setting within
    a mapping key named after that Manifest's kind ("lsst", "butler", etc.).
    """

    # Where another Manifest's fields can be set at the Step level, that model
    # is transformed via the `SubfieldManifest` class which produces
    # a new version of the target model where all fields are optional. The
    # original model maintains the required nature of these fields. This allows
    # the targeted overriding of specific manifest-field values at the step
    # level while preserving a comprehensive validation schema.

    model_config = SPEC_CONFIG
    predicates: Annotated[
        MutableSequence[str], PlainSerializer(lambda x: " AND ".join(x), return_type=str)
    ] = Field(
        default_factory=list,
        title="Data Query Predicates",
        description="A list of Butler data query predicates specific to the Step. "
        "These will be `AND`-ed together with data query predicates pushed down "
        "from the Campaign-level Butler Manifest.",
        serialization_alias="data_query",
        examples=[["instrument='LSSTCam'", "skymap='lsst_cells_v2'"]],
    )
    groups: (
        Annotated[
            StepGroupsValuesSpec,
            Field(
                title="Split by Values",
                description="Split step data IDs by value identity or range.",
                examples=[
                    {"groups": {"dimension": "tract", "split_by": "values", "values": [1, 2, 3, 4, 5]}}
                ],
            ),
        ]
        | Annotated[
            StepGroupsQuerySpec,
            Field(
                title="Split by Butler Query",
                description="Split step data IDs by partitioning the results of a Butler Query.",
                examples=[],
            ),
        ]
        | Annotated[
            None,
            Field(
                title="No Group Splitting",
                description="Do not split step data IDs into Groups. The step will use a single Group.",
                examples=[{"groups": None}],
            ),
        ]
    ) = None

    group_nonce: Literal["ordinal", "random"] = Field(
        default="ordinal",
        title="Group Naming Convention",
        description="The method used to name group nodes for this step. "
        "If 'ordinal', groups will be named with a three-digit zero-padded number, e.g., `*_001`; "
        "if 'random' then a portion of the group's hexadecimal id is used in the name.",
    )
    bps: SubfieldManifest[BpsSpec] = Field(
        title="Step BPS Configuration",
        description="Any BPS Manifest fields can be set at the step level.",
    )

    butler: (
        Annotated[
            SubfieldManifest[ButlerSpec],
            Field(
                title="Step Butler Configuration",
                description="Any Butler Manifest fields can be set at the step level.",
            ),
        ]
        | Annotated[
            None,
            Field(
                title="Null Configuration",
                description="A Butler config is not mandatory for a Step configuration",
            ),
        ]
    ) = None

    lsst: (
        Annotated[
            SubfieldManifest[LsstSpec],
            Field(
                title="Step LSST Configuration",
                description="Any LSST Manifest fields can be set at the step level.",
            ),
        ]
        | Annotated[
            None,
            Field(
                title="Null Configuration",
                description="An LSST config is not mandatory for a Step configuration",
            ),
        ]
    ) = None

    wms: (
        Annotated[
            SubfieldManifest[WmsSpec],
            Field(
                title="Step WMS Configuration",
                description="Any WMS Manifest fields can be set at the step level.",
            ),
        ]
        | Annotated[
            None,
            Field(
                title="Null Configuration",
                description="A WMS config is not mandatory for a Step configuration",
            ),
        ]
    ) = None

    site: (
        Annotated[
            SubfieldManifest[FacilitySpec],
            Field(
                title="Step Site Configuration",
                description="Any Site Manifest fields can be set at the step level.",
            ),
        ]
        | Annotated[
            None,
            Field(
                title="Null Configuration",
                description="A Site config is not mandatory for a Step configuration",
            ),
        ]
    ) = None


class StepManifest(LibraryManifest[StepSpec]): ...


class BreakpointSpec(ManifestSpec):
    """Configuration model for a Breakpoint node. Breakpoint nodes do not have
    any configurable attributes.
    """

    model_config = SPEC_CONFIG


class BreakpointManifest(LibraryManifest[BreakpointSpec]): ...
