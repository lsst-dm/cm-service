"""Model library describing the runtime data model of a Library Manifest for a
BPS operation.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from . import LibraryManifest, ManifestSpec


class BpsSpec(ManifestSpec):
    """Model specification for a BPS Manifest configuration document. Only
    the first-class attributes of this model will be available when rendering
    a campaign template.
    """

    model_config = SPEC_CONFIG
    # FIXME the pipeline yaml should be optional in a library or campaign
    # manifest but mandatory in a step.
    pipeline_yaml: str | None = Field(
        default=None,
        description="The absolute path to a Pipeline YAML specification file with optional anchor. "
        "The path must begin with a `/` or a `${...}` environment variable.",
        pattern="^(/|\\$\\{.*\\})(.*)(\\.yaml)(#.*)?$",
    )
    variables: dict[str, str] | None = Field(
        default=None,
        description=(
            "A mapping of name-value string pairs used to define addtional "
            "top-level BPS substitution variables. Note that the values are quoted in the "
            "output."
        ),
    )
    include_files: list[str] | None = Field(default=None)
    literals: dict[str, Any] | None = Field(
        default=None,
        description=(
            "A mapping of arbitrary top-level mapping sections to be added as additional literal YAML, "
            "e.g., `finalJob`."
        ),
    )
    environment: dict[str, str] | None = Field(
        default=None,
        description=(
            "A mapping of name-value string pairs used to defined additional "
            "values under the `environment` heading."
        ),
    )
    payload: dict[str, str] | None = Field(
        default=None,
        description=(
            "A mapping of name-value string pairs used to define BPS payload "
            "options. Note that these values are generated from other configuration "
            "sources at runtime."
        ),
    )
    extra_init_options: str | None = Field(
        default=None, description="Options added to the end of pipetaskinit"
    )
    extra_qgraph_options: str | None = Field(
        default=None, description="Options added to the end of command line when creating a quantumgraph."
    )
    extra_run_quantum_options: str | None = Field(
        default=None, description="Options added to the end of pipetask command to run a quantum"
    )
    extra_update_qgraph_options: str | None = Field(default=None)
    clustering: dict[str, Any] | None = Field(
        default=None,
        description=(
            "A mapping of clustering directives, added as literal YAML under the `clustering` heading."
        ),
    )


class BpsManifest(LibraryManifest[BpsSpec]): ...
