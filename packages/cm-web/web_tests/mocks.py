"""Mocks of the CM Service API's write operations, which the fake API does not
fake, for tests that need them to behave like the API and its daemon.
"""

import json
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import NamedTuple
from uuid import uuid4

import respx
from httpx import Request, Response, codes

from .conftest import API_BASE_URL, FakeCMService


def mock_campaign_status_change(cm_api: FakeCMService, campaign: dict) -> respx.Route:
    """Mock the campaign PATCH API for a status change.

    Like the API, the response is "202 Accepted" with a "StatusUpdate" link to
    the activity log entries for the request. The status change itself is
    assumed to complete at once, and is recorded in the campaign's activity
    log.
    """

    def patch(request: Request) -> Response:
        new_status = json.loads(request.content)["status"]
        request_id = str(uuid4())
        cm_api.add_log(
            campaign["id"],
            from_status=campaign["status"],
            to_status=new_status,
            request_id=request_id,
        )
        campaign["status"] = new_status
        status_update = f"{API_BASE_URL}/campaigns/{campaign['id']}/logs?request-id={request_id}"
        return Response(codes.ACCEPTED, json=campaign, headers={"StatusUpdate": status_update})

    return cm_api.router.patch(f"/campaigns/{campaign['id']}").mock(side_effect=patch)


class NodeStatusChange:
    """A mock of the node PATCH API for a status change, whose completion is
    controlled by the test.

    Like the API, the response is "202 Accepted" with a "StatusUpdate" link to
    the activity log entries for the request, which has none until the test
    calls `complete()` to apply the status change and record it in the
    campaign's activity log, as the daemon would.
    """

    def __init__(self, cm_api: FakeCMService, node: dict) -> None:
        self.cm_api = cm_api
        self.node = node
        self.requests: list[tuple[str, str, str]] = []
        self.route = cm_api.router.patch(f"/nodes/{node['id']}").mock(side_effect=self.patch)

    def patch(self, request: Request) -> Response:
        request_id = str(uuid4())
        operator = request.headers.get("X-Auth-Request-User", "anonymous")
        self.requests.append((request_id, json.loads(request.content)["status"], operator))
        status_update = f"{API_BASE_URL}/campaigns/{self.node['namespace']}/logs?request-id={request_id}"
        return Response(codes.ACCEPTED, json=self.node, headers={"StatusUpdate": status_update})

    def complete(self, finished_at: datetime, detail: dict | None = None) -> dict:
        """Apply the requested status change, as the daemon would, recording
        any detail of the transition in its activity log entry.
        """
        request_id, to_status, operator = self.requests.pop(0)
        log = self.cm_api.add_log(
            self.node["namespace"],
            node_id=self.node["id"],
            operator=operator,
            from_status=self.node["status"],
            to_status=to_status,
            detail=detail,
            request_id=request_id,
            created_at=finished_at - timedelta(seconds=2),
            finished_at=finished_at,
        )
        self.node["status"] = to_status
        return log


class Transition(NamedTuple):
    """A node transition applied by the daemon, or by the RPC "process" API on
    its behalf.
    """

    to_status: str
    finished_at: datetime
    detail: dict | None = None
    """The detail of the transition's activity log entry, e.g., an error."""
    metadata: dict | None = None
    """Metadata recorded on the node by the transition, e.g., a BPS report."""
    side_effect: Callable[[], object] | None = None
    """A change to the campaign made by the transition, e.g., the expansion
    of a step's subgraph when it prepares.
    """


def apply_transition(
    cm_api: FakeCMService, node: dict, transition: Transition, *, request_id: str | None = None
) -> dict:
    """Apply a transition to a node as the daemon does, including its side
    effects, and record it in the campaign's activity log. Activity on behalf
    of a client request has its request id; the daemon's own activity has none.
    """
    if transition.side_effect is not None:
        transition.side_effect()
    if transition.metadata:
        node["metadata"] |= transition.metadata
    log = cm_api.add_log(
        node["namespace"],
        node_id=node["id"],
        operator="daemon",
        from_status=node["status"],
        to_status=transition.to_status,
        detail=transition.detail,
        request_id=request_id,
        created_at=transition.finished_at - timedelta(seconds=2),
        finished_at=transition.finished_at,
    )
    node["status"] = transition.to_status
    return log


def daemon_tick(cm_api: FakeCMService, campaign_id: str, transitions: Mapping[str, Transition]) -> None:
    """Apply a transition to each of the named nodes of a campaign, as the
    daemon does when it considers a running campaign, evolving its processable
    nodes in parallel.
    """
    nodes = {n["name"]: n for n in cm_api.nodes.values() if n["namespace"] == campaign_id}
    for name, transition in transitions.items():
        apply_transition(cm_api, nodes[name], transition)


def campaign_transition(
    cm_api: FakeCMService,
    campaign: dict,
    to_status: str,
    finished_at: datetime,
    *,
    operator: str = "daemon",
    request_id: str | None = None,
) -> dict:
    """Apply a status change to a campaign, as the daemon does, e.g., when it
    finishes a campaign whose END node is accepted, or on behalf of a user's
    request to pause or resume it, and record it in the campaign's activity
    log.
    """
    log = cm_api.add_log(
        campaign["id"],
        operator=operator,
        from_status=campaign["status"],
        to_status=to_status,
        request_id=request_id,
        created_at=finished_at - timedelta(seconds=2),
        finished_at=finished_at,
    )
    campaign["status"] = to_status
    return log


class NodeProcessRpc:
    """A mock of the RPC "process" API, which evolves a node of a paused
    campaign through its next transition, as the daemon would.

    Like the API, the response is "202 Accepted" with a "StatusUpdate" link to
    the activity log entries for the request. Each request applies the next of
    the given transitions at once.
    """

    def __init__(self, cm_api: FakeCMService, node: dict, transitions: list[Transition]) -> None:
        self.cm_api = cm_api
        self.node = node
        self.transitions = transitions
        self.route = cm_api.router.post("/rpc/process").mock(side_effect=self.process)

    def process(self, request: Request) -> Response:
        assert json.loads(request.content) == {"node_id": self.node["id"]}
        request_id = str(uuid4())
        apply_transition(self.cm_api, self.node, self.transitions.pop(0), request_id=request_id)
        status_update = f"{API_BASE_URL}/campaigns/{self.node['namespace']}/logs?request-id={request_id}"
        return Response(codes.ACCEPTED, json=None, headers={"StatusUpdate": status_update})


class NodeCreation:
    """A mock of the node POST API, which creates a node from a manifest in
    the fake API, as the next version of any node with its name.
    """

    def __init__(self, cm_api: FakeCMService) -> None:
        self.cm_api = cm_api
        self.created: list[dict] = []
        self.route = cm_api.router.post("/nodes/").mock(side_effect=self.post)

    def post(self, request: Request) -> Response:
        manifest = json.loads(request.content)
        metadata = manifest["metadata"]
        namespace = metadata["namespace"]
        versions = [
            n["version"]
            for n in self.cm_api.nodes.values()
            if n["namespace"] == namespace and n["name"] == metadata["name"]
        ]
        node = self.cm_api.add_node(
            namespace,
            metadata["name"],
            kind=metadata.get("kind", "other"),
            version=max(versions, default=int(metadata.get("version", 0))) + 1,
            configuration=manifest["spec"],
        )
        node["metadata"] |= metadata
        self.created.append(node)
        headers = {
            "Self": f"{API_BASE_URL}/nodes/{node['id']}",
            "Campaign": f"{API_BASE_URL}/campaigns/{namespace}",
        }
        return Response(codes.OK, json=node, headers=headers)


class GraphInsert:
    """A mock of the campaign graph node PATCH API for an insert operation,
    which puts Node[1] immediately after Node[0] in the graph: Node[0]'s
    outbound edges are moved to Node[1] and Node[1] becomes Node[0]'s only
    successor.

    Like the API, the graph of a campaign that is not paused cannot be
    modified, which is a "409 Conflict".
    """

    def __init__(self, cm_api: FakeCMService, campaign: dict) -> None:
        self.cm_api = cm_api
        self.campaign = campaign
        self.route = cm_api.router.patch(
            path__regex=rf"/campaigns/{campaign['id']}/graph/nodes/(?P<node_0_id>[^/]+)$"
        ).mock(side_effect=self.patch)

    def patch(self, request: Request, node_0_id: str) -> Response:
        assert request.url.params["operation"] == "insert"
        node_1_id = request.url.params["add-node"]
        if self.campaign["status"] != "paused":
            detail = f"Graph for Campaign in status {self.campaign['status']} cannot be modified."
            return Response(codes.CONFLICT, json={"detail": detail})

        edges = self.cm_api.edges[self.campaign["id"]]
        successors = [target for source, target in edges if source == node_0_id]
        edges[:] = [(s, t) for s, t in edges if s != node_0_id]
        edges.append((node_0_id, node_1_id))
        edges.extend((node_1_id, successor) for successor in successors)
        return Response(codes.NO_CONTENT)


class ManifestLoader:
    """A mock of the API's manifest POST operations as a campaign is saved
    from a list of manifests: campaigns, nodes, edges, and other manifests are
    created in the fake API.

    Like the API, a new campaign is created with its START and END nodes but
    no edges, and an edge's source and target are the names of the latest
    versions of nodes in its campaign.
    """

    def __init__(self, cm_api: FakeCMService) -> None:
        self.cm_api = cm_api
        self.manifests: list[dict] = []
        self.node_creation = NodeCreation(cm_api)
        cm_api.router.post("/campaigns/").mock(side_effect=self.post_campaign)
        cm_api.router.post("/edges/").mock(side_effect=self.post_edge)
        cm_api.router.post("/manifests/").mock(side_effect=self.post_manifest)
        self.node_creation.route.side_effect = self.post_node

    def post_campaign(self, request: Request) -> Response:
        manifest = json.loads(request.content)
        self.manifests.append(manifest)
        campaign = self.cm_api.add_campaign(
            manifest["metadata"]["name"],
            owner=request.headers.get("X-Auth-Request-User", "anonymous"),
            configuration=manifest.get("spec") or {},
        )
        self.cm_api.edges[campaign["id"]] = []
        return Response(codes.OK, json=campaign)

    def post_node(self, request: Request) -> Response:
        self.manifests.append(json.loads(request.content))
        return self.node_creation.post(request)

    def post_edge(self, request: Request) -> Response:
        manifest = json.loads(request.content)
        self.manifests.append(manifest)
        namespace = manifest["metadata"]["namespace"]

        def latest(name: str) -> str:
            versions = [
                n for n in self.cm_api.nodes.values() if n["namespace"] == namespace and n["name"] == name
            ]
            return max(versions, key=lambda n: n["version"])["id"]

        edge = (latest(manifest["spec"]["source"]), latest(manifest["spec"]["target"]))
        self.cm_api.edges[namespace].append(edge)
        return Response(codes.OK, json={"name": manifest["metadata"]["name"], "namespace": namespace})

    def post_manifest(self, request: Request) -> Response:
        manifest = json.loads(request.content)
        self.manifests.append(manifest)
        created = self.cm_api.add_manifest(
            manifest["kind"],
            manifest["metadata"]["name"],
            namespace=manifest["metadata"]["namespace"],
            spec=manifest.get("spec") or {},
        )
        # like the API, the manifest keeps its metadata, e.g., its labels
        created["metadata"] |= manifest["metadata"]
        return Response(codes.OK, json=created)
