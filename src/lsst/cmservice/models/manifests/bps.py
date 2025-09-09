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

    pipeline_yaml: str | None = Field(default=None)
    variables: dict[str, str] | None = Field(default=None)
    include_files: list[str] | None = Field(default=None)
    literals: dict[str, str] | None = Field(default=None)
    environment: dict[str, str] | None = Field(default=None)
    payload: dict[str, str] | None = Field(default=None)
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
    clustering: dict[str, Any] | None = Field(default=None)


class BpsManifest(LibraryManifest[BpsSpec]): ...
