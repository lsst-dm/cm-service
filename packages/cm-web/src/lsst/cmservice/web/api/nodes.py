"""Module containing classes, methods, and functions related to API actions
targeting Node resources.
"""

from typing import Literal

from httpx import HTTPStatusError, Response, codes
from nicegui import app, ui

from ..lib.client_factory import CLIENT_FACTORY
from .activity import wait_for_activity_to_complete


async def get_one_node(id: str, namespace: str | None) -> Response | None:
    """Get a single Node by its id or name+namespace."""
    # TODO get nodes and fallback to manifests on 404?
    url = f"/nodes/{id}"
    if namespace is not None:
        url += f"?campaign-id={namespace}"
    async with CLIENT_FACTORY.aclient() as client:
        r = await client.get(url)
        if r.status_code == codes.NOT_FOUND:
            return None
        r.raise_for_status()
        return r


async def describe_one_node(id: str) -> dict:
    """Describes a single node by its id.

    The "description" of a node includes its manifest and any activity logs
    associated with it. As a side effect, this function updates the client
    storage with the status of the node, which may propogate to bound elements
    and trigger updates.
    """
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

    # cache node and campaign
    campaign_id = data["node"]["namespace"]
    if app.storage.client["state"].nodes.get(id) is None:
        app.storage.client["state"].nodes[id] = {}
    else:
        app.storage.client["state"].nodes[id]["status"] = data["node"]["status"]

    if app.storage.client["state"].campaigns.get(campaign_id) is None:
        app.storage.client["state"].campaigns[campaign_id] = {}
    return data


async def replace_node(n0: str, n1: str, namespace: str) -> Response:
    """Supports the node PUT api to replace a node in a graph with a different
    one.
    """
    async with CLIENT_FACTORY.aclient() as client:
        try:
            r = await client.put(f"/campaigns/{namespace}/graph/nodes/{n0}?with-node={n1}")
            r.raise_for_status()
            ui.notify("Node replaced.")
        except HTTPStatusError as e:
            match e.response:
                case Response(status_code=codes.CONFLICT):
                    ui.notify("Campaign must be paused before modification", type="negative")
                case _:
                    raise
        return r


async def insert_or_append_node(
    n0: str, n1: str, namespace: str, operation: Literal["append", "insert"]
) -> Response:
    """Supports the node PATCH api to insert a new node in an existing campaign
    graph.
    """
    async with CLIENT_FACTORY.aclient() as client:
        try:
            r = await client.patch(
                f"/campaigns/{namespace}/graph/nodes/{n0}?add-node={n1}&operation={operation}"
            )
            r.raise_for_status()
            ui.notify("Node replaced.")
        except HTTPStatusError as e:
            match e.response:
                case Response(status_code=codes.CONFLICT):
                    ui.notify("Campaign must be paused before modification", type="negative")
                case _:
                    raise
        return r


async def fast_forward_node(n0: str) -> None:
    """Callback function for manually advancing a single Node's state machine
    using the CM RPC "process" api. A Node in a paused campaign may have trans-
    port controls present (e.g., a forward button).
    """
    async with CLIENT_FACTORY.aclient() as client:
        try:
            r = await client.post("/rpc/process", json={"node_id": n0})
            r.raise_for_status()
        except HTTPStatusError as e:
            match e.response:
                case Response(status_code=codes.UNPROCESSABLE_ENTITY):
                    ui.notify(r.text, type="negative")
                case Response(status_code=codes.INTERNAL_SERVER_ERROR):
                    ui.notify("Attempt failed with a Server Error", type="negative")
                case _:
                    raise
        status_update_url = r.headers["StatusUpdate"]
        node_cache: dict = app.storage.client["state"].nodes
        node_cache[n0]["label"] = "Advancing..."
        node_cache[n0]["icon"] = "hourglass_empty"
        ui.notify(status_update_url, close_button="OK", timeout=5000, spinner=True)
        # . await wait_for_activity_to_complete(status_update_url)
        node_cache[n0]["label"] = ""
        node_cache[n0]["icon"] = "fast_forward"


async def retry_restart_node(
    n0: str, *, force: bool = False, reset: bool = False, accept: bool = False, reject: bool = False
) -> None:
    """A group node in a failed state can be "restarted" if the BPS milestone
    is reached, i.e., a submit directory has been discovered and a qg file
    exists in that submit directory. Otherwise, a node can be "retried" if the
    BPS milestone has not been reached.

    The CM API server decides whether a node can be restarted or not. A client
    may PATCH the node's status to "ready" with a ``force`` option to affect a
    restart.

    Parameters
    ----------
    force : bool
        If True, the retry is a restart instead.

    reset : bool
        If True, the operation is a reset (the desired state is ``waiting``).
        If False (default), the operation is a retry/restart (the desired state
        if ``ready``).

    accept : bool
        If True, the node is unconditionally accepted, but ``force`` must also
        be set.

    reject : bool
        If True, the node is unconditionally failed, but ``force`` must also
        be set.
    """
    # TODO refactor these parameters into a FlagEnum
    url = f"/nodes/{n0}"
    retry_or_restart = "Restarting" if force else "Retrying"
    retry_or_restart = "Resetting" if reset else retry_or_restart
    retry_or_restart = "Accepting" if all([force, accept]) else retry_or_restart
    retry_or_restart = "Rejecting" if all([force, reject]) else retry_or_restart
    target_state = "waiting" if reset else "ready"
    target_state = "accepted" if all([force, accept]) else target_state
    target_state = "failed" if all([force, reject]) else target_state

    async with CLIENT_FACTORY.aclient() as client:
        n = ui.notification(timeout=None)
        try:
            r = await client.patch(
                url,
                headers={"Content-Type": "application/merge-patch+json"},
                json={"status": target_state, "force": force},
            )
            r.raise_for_status()
            n.spinner = True
            n.type = "ongoing"
            n.message = f"{retry_or_restart} node..."
        except HTTPStatusError as e:
            n.type = "negative"
            n.timeout = 5.0
            match e.response:
                case Response(status_code=codes.UNPROCESSABLE_ENTITY):
                    n.message = r.text
                case Response(status_code=codes.INTERNAL_SERVER_ERROR):
                    n.message = "Attempt failed with a Server Error"
                case _:
                    raise
            return None

        status_update_url = r.headers["StatusUpdate"]
        await wait_for_activity_to_complete(status_update_url, n)


async def node_activity_logs(id: str) -> list[dict]:
    # FIXME this API needs to be sorted by `finished_at`
    async with CLIENT_FACTORY.aclient() as session:
        r = await session.get(f"/logs?node={id}")
        r.raise_for_status()
    return r.json()
