from typing import Any

from lsst.cmservice.models.manifests.manifests import (
    ArtifactSpec,
    BpsSpec,
    ButlerSpec,
    FacilitySpec,
    LsstSpec,
    ManifestSpec,
    StepSpec,
    WmsSpec,
)

STEP_MANIFEST_TEMPLATE: dict[str, Any] = {
    "apiVersion": "io.lsst.cmservice/v1",
    "kind": "node",
    "metadata": {},
    "spec": {},
}


KIND_TO_SPEC: dict[str, type[ManifestSpec]] = {
    "artifact": ArtifactSpec,
    "bps": BpsSpec,
    "wms": WmsSpec,
    "lsst": LsstSpec,
    "site": FacilitySpec,
    "butler": ButlerSpec,
    "step": StepSpec,
}

DEFAULT_NOTIFICATION_FILTERS = [
    ("start", "*", "running"),
    ("end", "running", "*"),
    ("*", "*", "failed"),
    ("breakpoint", "*", "running"),
]
