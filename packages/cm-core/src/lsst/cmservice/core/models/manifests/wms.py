"""Model library describing the runtime data model of a Library Manifest for a
Work Management or Batch system used by a Campaign for compute resources.

Configuration provided by a WMS manifest generally align with the WMS config-
uration block of a BPS submit file.
"""

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import AliasChoices, Field

from . import LibraryManifest, ManifestSpec


class WmsSpec(ManifestSpec):
    batch_system: Annotated[
        str, Literal["htcondor", "panda"], Field(validation_alias=AliasChoices("batch_system", "wms"))
    ]
    service_class: Annotated[str, Field(description="wmsServiceClass used by the batch system")]
    environment: Mapping = Field(
        default_factory=dict, description="A mapping of environment variables to set prior to bps submit."
    )


class WmsManifest(LibraryManifest[WmsSpec]): ...
