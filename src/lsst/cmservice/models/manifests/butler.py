"""Model library describing the runtime data model of a Library Manifest for a
Butler, which aligns a Butler repo with a data query and a set of collections
for a Campaign.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field

from . import LibraryManifest, ManifestSpec


class ButlerSpec(ManifestSpec):
    """Spec model for a Butler Manifest."""

    collections: ButlerCollectionsSpec
    predicates: Sequence[str] = Field(default_factory=list)
    repo: str = Field(description="Name of a Butler known to the application's Butler Factory.")
    include_files: list[str] | None = Field(default=None)


class ButlerCollectionsSpec(BaseModel):
    """Specification for the definition of Butler collections used throughout
    a campaign. This model is part of the "spec" of a Butler Library Manifest.
    """

    campaign_input: list[str] = Field(
        description="The campaign source collection",
        default_factory=list,
        validation_alias=AliasChoices("campaign_input", "in"),
    )
    ancillary: list[str] = Field(default_factory=list)
    campaign_public_output: str = Field(
        description="The public output collection for this Campaign.",
        default_factory=lambda: uuid4().__str__(),
        validation_alias=AliasChoices("campaign_public_output", "out"),
    )
    campaign_output: str | None = Field(
        default=None, description="The private output collection for a campaign; {out}/output"
    )
    step_input: str | None = Field(default=None, description="{out}/{step}/input")
    step_output: str | None = Field(default=None, description="{out}/{step}_output")
    step_public_output: str | None = Field(default=None, description="{out}/{step}")
    group_output: str | None = Field(default=None, description="{out}/{step}/{group}")
    run: str | None = Field(
        default=None,
        description="The run collection affected by a Node's execution; {out}/{step}/{group}/{job}",
        validation_alias=AliasChoices("job_run", "run"),
    )


class ButlerManifest(LibraryManifest[ButlerSpec]): ...
