from httpx import HTTPStatusError, Response, codes
from nicegui import ui

from ..lib.client_factory import CLIENT_FACTORY


async def get_one_manifest(
    namespace: str,
    id: str | None = None,
    kind: str | None = None,
    name: str | None = None,
    version: int | None = None,
) -> Response | None:
    # Default URL when manifest id is used
    url = f"/manifests/{id}"

    if kind is not None:
        url = f"/campaigns/{namespace}/manifest/{kind}"
        if name is not None:
            url += f"/{name}"
            if version is not None:
                url += f"/{version}"

    async with CLIENT_FACTORY.aclient() as client:
        r = await client.get(url)
        if r.status_code == codes.NOT_FOUND:
            return None
        r.raise_for_status()
        return r


async def put_one_manifest(manifest_id: str, manifest_name: str, to_namespace: str) -> Response:
    """Copies a manifest into the designated target namespace."""
    url = f"/manifests/{manifest_id}"

    async with CLIENT_FACTORY.aclient() as client:
        r = await client.put(
            url,
            headers={
                "Namespace-Copy-Target": to_namespace,
                "Name-Copy-Target": manifest_name,
            },
        )
        r.raise_for_status()
        return r


async def put_manifest_list(manifests: list[dict]) -> bool:
    """Uploads a list of manifests. The manifests are not manipulated prior
    to being uploaded, and the manifests are not assumed to be related. The
    only ordering necessary is that "campaigns" must be first in the list in
    order to prepare any target namespaces for subsequent manifests.
    """
    # TODO sort manifests list by kind, campaigns first.
    async with CLIENT_FACTORY.aclient() as client:
        for manifest in manifests:
            match manifest["kind"]:
                case "campaign":
                    uri = "/campaigns"
                case "node":
                    uri = "/nodes"
                case "edge":
                    uri = "/edges"
                case _:
                    uri = "/manifests"
            try:
                r = await client.post(uri, json=manifest)
                r.raise_for_status()
            except HTTPStatusError as e:
                if e.response.status_code == codes.CONFLICT:
                    ui.notify("Campaign already exists, try changing the name", type="warning")
                    return False
                else:
                    ui.notify(f"Failed to save manifest: {manifest['metadata']['name']}", type="negative")
                    continue
    # A true response indicates success
    return True
