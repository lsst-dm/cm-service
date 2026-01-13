"""Model library describing the runtime data model of a Library Manifest for a
Butler, which aligns a Butler repo with a data query and a set of collections
for a Campaign.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field

from . import SPEC_CONFIG, LibraryManifest, ManifestSpec


class ButlerCollectionsSpec(BaseModel):
    """Specification for the definition of Butler collections used throughout
    a campaign. This model is part of the "spec" of a Butler Library Manifest.
    """

    model_config = SPEC_CONFIG
    campaign_input: list[str] = Field(
        description="The campaign source collection. The input collection list should not include environment"
        " or BPS variables that will be unknown to the CM Service.",
        default_factory=list,
        validation_alias=AliasChoices("campaign_input", "in"),
        examples=[["LSSTCam/defaults"]],
    )
    ancillary: list[str] = Field(
        default_factory=list,
        deprecated=True,
        description="A set of collections related to the campaign input collections that will be chained "
        "together to create a collection for the campaign.",
        examples=[["refcats", "skymaps"]],
    )
    campaign_public_output: str = Field(
        description="The final 'public' campaign *chained* collection; includes the `campaign_output` "
        "collection, the Campaign 'input' collection, and any other incidental collections created during "
        "the campaign (e.g., resource usage)",
        default_factory=lambda: uuid4().__str__(),
        validation_alias=AliasChoices("campaign_public_output", "out"),
        examples=["u/{operator}/{campaign}"],
    )
    campaign_output: str | None = Field(
        default=None,
        description="The 'private' output collection for a campaign; a *chained* collection of "
        "each step-specific *output* collection, which itself is a *chained* collection of each step-group's "
        "`run` collection.",
        examples=["u/{operator}/{campaign}/out"],
    )
    step_input: str | None = Field(
        default=None,
        description="The *chained* input collection for a step, usually consisting of the campaign input and "
        "any ancestor `step_output` collection."
        " This is used internally and generally does not need to be configured.",
        examples=["{campaign_public_output}/{step}/input"],
        json_schema_extra={"readOnly": True},
    )
    step_output: str | None = Field(
        default=None,
        description="The *chained* output collection for a step, usually consisting of each step-group's "
        "`run` collection."
        " This is used internally and generally does not need to be configured.",
        examples=["{campaign_public_output}/{step}_output"],
        json_schema_extra={"readOnly": True},
    )
    step_public_output: str | None = Field(
        default=None,
        description="The *chained* output collection that includes the `step_output` and additional step "
        "and/or campaign inputs."
        " This is used internally and generally does not need to be configured.",
        examples=["{campaign_public_output}/{step}"],
        json_schema_extra={"readOnly": True},
    )
    group_output: str | None = Field(
        default=None,
        description="A collection name associated with the `payload.output` BPS setting."
        " This is used internally and generally does not need to be configured.",
        examples=["{campaign_public_output}/{step}/{group_nonce}", "u/{operator}/{payloadName}"],
        json_schema_extra={"readOnly": True},
    )
    run: str | None = Field(
        default=None,
        description="The run collection created by a group's execution (the `payload.outputRun` BPS setting)."
        " This is used internally and generally does not need to be configured.",
        examples=["{out}/{step}/{group}/{job}"],
        validation_alias=AliasChoices("job_run", "run"),
        json_schema_extra={"readOnly": True},
    )


class ButlerSpec(ManifestSpec):
    """Configuration specification for a Butler Manifest. This is primarily
    used to manage collections and group splitting rules throughout a campaign,
    as well as populating the `payload` section of a BPS submission file.
    """

    model_config = SPEC_CONFIG
    collections: ButlerCollectionsSpec = Field(
        description="A butler configuration used to specify collections for "
        "various campaign operations. Of particular interest for a Butler"
        "manifest are `campaign_input` and `campaign_output`",
        examples=[
            {
                "campaign_input": ["LSSTCam/defaults"],
                "campaign_public_output": "u/{operator}/{campaign}",
                "campaign_output": "u/{operator}/{campaign}/out",
            }
        ],
    )
    predicates: Sequence[str] = Field(
        default_factory=list,
        description="A set of data query predicates shared with all users of"
        "this manifest. All predicate sets are `AND`-ed together for a final "
        "data query",
        examples=[
            ["instrument='LSSTCam'", "skymap='lsst_cells_v2'"],
        ],
    )
    repo: str = Field(
        description="Name of a Butler known to the application's Butler Factory.",
        examples=["/repo/main", "embargo"],
    )
    include_files: list[str] | None = Field(
        default=None,
        description="A list of files to be added to the BPS submission as include files "
        "that are specific to the use of this Butler.",
        examples=["${DRP_PIPE_DIR}/includes/butler/{butler-tuning}.yaml"],
    )


class ButlerManifest(LibraryManifest[ButlerSpec]): ...
