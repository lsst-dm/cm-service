from httpx import HTTPStatusError, Response
from nicegui import ui

from ..lib.client_factory import CLIENT_FACTORY


async def get_one_node(id: str, namespace: str | None) -> Response:
    # TODO get nodes and fallback to manifests on 404?
    url = f"/nodes/{id}"
    if namespace is not None:
        url += f"?campaign-id={namespace}"
    async with CLIENT_FACTORY.aclient() as client:
        try:
            r = await client.get(url)
            r.raise_for_status()
        except HTTPStatusError as e:
            match e.response:
                case Response(status_code=409):
                    ui.notify("Campaign must be paused before modification", type="negative")
                case _:
                    raise
        return r


async def describe_one_node(id: str) -> dict:
    data = {}
    async with CLIENT_FACTORY.aclient() as client:
        try:
            r = await client.get(f"/nodes/{id}")
            r.raise_for_status()
            data["node"] = r.json()
            r = await client.get(f"/logs?node={id}")
            r.raise_for_status()
            data["logs"] = r.json()
        except HTTPStatusError:
            raise
    return data


async def replace_node(n0: str, n1: str, namespace: str) -> Response:
    async with CLIENT_FACTORY.aclient() as client:
        try:
            r = await client.put(f"/campaigns/{namespace}/graph/nodes/{n0}?with-node={n1}")
            r.raise_for_status()
            ui.notify("Node replaced.")
        except HTTPStatusError as e:
            match e.response:
                case Response(status_code=409):
                    ui.notify("Campaign must be paused before modification", type="negative")
                case _:
                    raise
        return r
