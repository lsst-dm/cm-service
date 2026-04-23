"""Primitive models or skeletons for api models"""

STEP_MANIFEST_TEMPLATE: dict[str, str | dict] = {
    "apiVersion": "io.lsst.cmservice/v1",
    "kind": "node",
    "metadata": {},
    "spec": {},
}
