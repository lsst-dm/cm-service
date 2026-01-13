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
    """Spec model for the Groups definition of a step when a query-based
    splitter is involved.
    """

    model_config = SPEC_CONFIG
    split_by: Literal["query"]
    dataset: str = Field(description="The name of a dataset to query")
    dimension: str = Field(
        description="The name of a Butler dimension to associate with each "
        "grouping `value` to form a query predicate.",
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
    """Spec model for the range applied to the value field of a group spec."""

    model_config = SPEC_CONFIG
    min: int = Field(description="Minimum dimension value for a range")
    max: int = Field(description="Maximum dimension value for a range")
    endpoint: bool = Field(
        default=True,
        description="Whether the range is right-open or right-closed",
    )


class StepGroupsValuesSpec(ManifestSpec):
    """Spec model for the Groups definition of a step when a values-based
    splitter is involved.
    """

    model_config = SPEC_CONFIG
    split_by: Literal["values"]
    values: Sequence[str | int | Sequence[int] | StepGroupsValueRange]
    dimension: str = Field(
        description="The name of a Butler dimension to associate with each "
        "grouping `value` to form a query predicate.",
    )


class StepSpec(ManifestSpec):
    """Spec model for a Step Node.

    Where another Manifest's fields can be set at the Step level, that Manifest
    Spec model is transformed via the `SubfieldManifest` class which produces
    a new version of the target model where all fields are optional. The
    original model maintains the required nature of these fields. This allows
    the targeted overriding of specific manifest-field values at the step level
    while preserving a comprehensive validation schema.
    """

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
    )
    groups: StepGroupsValuesSpec | StepGroupsQuerySpec | None
    group_nonce: Literal["ordinal", "random"] = Field(
        default="ordinal",
        title="Group Naming Convention",
        description="The method used to name group nodes for this step. "
        "If 'ordinal', groups will be named with a three-digit zero-padded number, e.g., `*_001`; "
        "if 'random' then a portion of the group's hexadecimal id is used in the name.",
    )
    bps: SubfieldManifest[BpsSpec] | None = Field(
        default=None,
        title="Step BPS Configuration",
        description="Any BPS Manifest fields can be set at the step level.",
    )
    butler: SubfieldManifest[ButlerSpec] | None = Field(
        default=None,
        title="Step Butler Configuration",
        description="Any Butler Manifest fields can be set at the step level.",
    )
    lsst: SubfieldManifest[LsstSpec] | None = Field(
        default=None,
        title="Step LSST Configuration",
        description="Any LSST Manifest fields can be set at the step level.",
    )
    wms: SubfieldManifest[WmsSpec] | None = Field(
        default=None,
        title="Step WMS Configuration",
        description="Any WMS Manifest fields can be set at the step level.",
    )
    site: SubfieldManifest[FacilitySpec] | None = Field(
        default=None,
        title="Step Site Configuration",
        description="Any Site Manifest fields can be set at the step level.",
    )


class StepManifest(LibraryManifest[StepSpec]): ...
