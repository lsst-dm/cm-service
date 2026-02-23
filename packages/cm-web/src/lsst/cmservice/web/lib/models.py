from typing import Any

from lsst.cmservice.models.manifests.manifests import (
    BpsSpec,
    ButlerSpec,
    FacilitySpec,
    LsstSpec,
    ManifestSpec,
    StepSpec,
    WmsSpec,
)

STEP_SPEC_TEMPLATE: dict[str, Any] = {
    "bps": {
        "pipeline_yaml": "${DRP_PIPE_DIR}/path/to/pipeline.yaml#anchor",
    },
    "groups": None,
    "predicates": [],
}


STEP_MANIFEST_TEMPLATE: dict[str, Any] = {
    "apiVersion": "io.lsst.cmservice/v1",
    "kind": "node",
    "metadata": {},
    "spec": {},
}


KIND_TO_SPEC: dict[str, type[ManifestSpec]] = {
    "bps": BpsSpec,
    "wms": WmsSpec,
    "lsst": LsstSpec,
    "site": FacilitySpec,
    "butler": ButlerSpec,
    "step": StepSpec,
}
