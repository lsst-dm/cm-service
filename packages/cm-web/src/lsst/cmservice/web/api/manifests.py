from httpx import Response, codes

from ..lib.client import http_client


def get_one_manifest(
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

    with http_client() as client:
        r = client.get(url)
        if r.status_code == codes.NOT_FOUND:
            return None
        r.raise_for_status()
        return r


def put_one_manifest(manifest_id: str, manifest_name: str, to_namespace: str) -> Response:
    """Copies a manifest into the designated target namespace."""
    url = f"/manifests/{manifest_id}"

    with http_client() as client:
        r = client.put(
            url,
            headers={
                "Namespace-Copy-Target": to_namespace,
                "Name-Copy-Target": manifest_name,
            },
        )
        r.raise_for_status()
        return r
