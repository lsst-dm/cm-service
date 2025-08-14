from collections.abc import Mapping, MutableSequence, Sequence
from typing import Annotated, Literal

from pydantic import Field, PlainSerializer

from . import LibraryManifest, ManifestSpec


class GroupedStepGroupsSpec(ManifestSpec):
    """Spec model for the Groups definition of a Grouped Step's configuration
    which specifies the parameters by which a dimension is split. The
    attributes of this model are used to construct a `Splitter` when the Step
    is prepared.
    """

    split_by: Literal["values", "query"]
    values: Sequence[str | int | Sequence[str | int] | Mapping]
    field: str
    dataset: str
    min_groups: int
    max_size: int


class GroupedStepSpec(ManifestSpec):
    """Spec model for a Node of kind GroupedStep."""

    pipeline_yaml: Annotated[
        str,
        Field(
            description="The absolute path to a Pipeline YAML specification file with optional anchor.",
            examples=[
                "${DRP_PIPE_DIR}/pipelines/LSSTCam/nightly-validation.yaml#step1a-single-visit-detectors"
            ],
        ),
    ]
    predicates: Annotated[
        MutableSequence[str], PlainSerializer(lambda x: " AND ".join(x), return_type=str)
    ] = Field(serialization_alias="data_query")
    groups: GroupedStepGroupsSpec | None


class GroupedStepManifest(LibraryManifest[GroupedStepSpec]): ...
