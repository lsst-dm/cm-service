"""Shared conftest module for cm-web tests.

These fixtures let the web application be tested without a CM Service API or
database. HTTP requests made through the cm-web client factory are intercepted
by a respx router, and read requests are answered from the in-memory state of
a `FakeCMService`. Write requests (POST, PUT, PATCH, DELETE) are not faked; a
test that expects one should register a route for it on `cm_api.router` so it
can assert on the request. Any request without a matching route fails the test.

Note that respx is built on httpx, so route side effects receive and return
`httpx` (not `httpx2`) request and response objects; respx translates these
for the `httpx2` clients used by the application.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator, Callable, Generator, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from typing import Any
from uuid import UUID, uuid5

import httpx
import networkx as nx
import pytest
import respx
from httpx import Request, Response, codes
from nicegui import app, core
from nicegui.storage import Storage
from nicegui.testing.user import User
from nicegui.testing.user_simulation import user_simulation

from lsst.cmservice.models.db.campaigns import ActivityLog, Campaign, CampaignSummary, Manifest, Node
from lsst.cmservice.models.enums import DEFAULT_NAMESPACE
from lsst.cmservice.models.lib.graph import graph_to_dict
from lsst.cmservice.web.api import activity
from lsst.cmservice.web.lib.client_factory import CLIENT_FACTORY, ClientFactory

API_BASE_URL = "http://cm-service.test/v2"
"""Base URL of the fake CM Service API."""

MAIN_FILE = Path(__file__).parent / "main.py"
"""NiceGUI main file used by the simulated `user` fixture."""

AUTH_HEADER = "X-Auth-Request-User"
"""Header by which the ingress identifies the user to the application."""

SERVICE_SOURCE = "/opt/lsst/software/cm-service/src/lsst/cmservice"
"""An illustrative location of the CM Service source in a deployment."""


def runtime_error_detail(message: str, *, module: str, line: int, code: str) -> str:
    """The error the daemon reports for a ``RuntimeError`` raised during a node
    transition, in the form produced by ``event_error_heuristic``.
    """
    return dedent(f"""\
        ## Transition Failed
        *An error occurred during state transition:*

        **RuntimeError** : Unspecified run-time error.

        ```
        {message}
        ```

        *This error occurred at:*

        module: {SERVICE_SOURCE}/{module}

        line: {line}

        code: {code}
    """)


def sulaco_group_configuration(group_name: str) -> dict:
    """The configuration of a group of the sulaco campaign, as baked from its
    step's configuration chain when the step prepares: in particular, the
    Butler collections for the group's output and its BPS run, and its BPS
    options.
    """
    step_name = group_name.rsplit("_group_", 1)[0]
    group_output = f"u/yutani/sulaco/{step_name}/{group_name.rsplit('_', 1)[-1]}"
    return {
        "butler": {
            "repo": "/repo/mock",
            "collections": {
                "step_input": f"u/yutani/sulaco/{step_name}/input",
                "group_output": group_output,
                "run": f"{group_output}/run",
            },
        },
        "bps": {
            "pipeline_yaml": "${WEYLAND_YUTANI}/colonial_marines.yaml#" + step_name,
            "extra_qgraph_options": [],
        },
    }


STATUS_FILL_COLORS = {
    "waiting": "#058b8c",  # dark blue
    "ready": "#00babc",  # light blue
    "running": "#ffc036",  # light orange
    "accepted": "#019305",  # dark green
    "failed": "#cf4040",  # dark red
}
"""The expected mermaid fill color of a campaign graph node by node status,
from the application's palette.
"""

WALTER_PREPARE_ERROR = runtime_error_detail(
    "Predecessor collect step has no output collection",
    module="machines/nodes/steps.py",
    line=354,
    code='raise RuntimeError("Predecessor collect step has no output collection")',
)
"""The error reported for the covenant campaign's walter step, which failed to
prepare.
"""

HUDSON_ARTIFACT_PATH = "/nonexistent/cm-artifacts/sulaco/hudson"
"""A placeholder artifact path for the sulaco campaign's hudson step."""

HUDSON_GROUP_FINISH_ERROR = runtime_error_detail(
    "WMS Job is Failed",
    module="machines/nodes/group.py",
    line=496,
    code="raise RuntimeError(msg)",
)
"""The error reported for a group of the sulaco campaign's hudson step whose
BPS report, as checked for its finish, has the workflow failed.
"""

HUDSON_FINISH_ERROR = runtime_error_detail(
    "Job Abnormally Terminated",
    module="common/htcondor.py",
    line=364,
    code="raise RuntimeError(msg)",
)
"""The error reported for the sulaco campaign's hudson step, whose HTCondor job
terminated with a non-zero exit code, as found by the check for its finish.
"""


def _dump(model: Any) -> dict:
    """Serialize a cm-models object the same way the API would."""
    return model.model_dump(mode="json", by_alias=True)


class FakeCMService:
    """An in-memory stand-in for the read side of the CM Service API.

    Objects added with the ``add_*`` methods are validated with the cm-models
    classes and served with the same shapes, headers, and pagination behavior
    as the real API. The state attributes may also be modified directly.

    Every route is named so a test can override its behavior, e.g.,
    ``cm_api.router.routes["campaign"].respond(500)``.
    """

    def __init__(self, router: respx.Router) -> None:
        self.router = router
        self.campaigns: dict[str, dict] = {}
        self.nodes: dict[str, dict] = {}
        self.edges: dict[str, list[tuple[str, str]]] = {}
        self.manifests: dict[str, dict] = {}
        self.logs: list[dict] = []
        # like the API's database, which is created with a "default" label
        self.notifications: list[dict] = [
            {
                "name": "default",
                "kind": "default",
                "configuration": {
                    "filters": ["start:*:running", "end:running:*", "*:*:failed", "breakpoint:*:running"]
                },
            }
        ]
        self.schedules: list[dict] = []
        self._register_routes()

    # -- state builders --------------------------------------------------- #

    def add_campaign(
        self,
        name: str,
        *,
        nodes: Iterable[str] | Mapping[str, str] = (),
        status: str = "paused",
        start_status: str = "waiting",
        owner: str = "testuser",
        configuration: dict | None = None,
    ) -> dict:
        """Add a campaign whose graph is a linear chain of step nodes between
        the campaign's START and END nodes.

        The step nodes are given by name, or as a mapping of name to status;
        otherwise nodes are "waiting". The START node should be "accepted" for
        a campaign that has moved on to processing its steps.
        """
        if not isinstance(nodes, Mapping):
            nodes = dict.fromkeys(nodes, "waiting")
        campaign = _dump(
            Campaign.model_validate(
                {
                    "id": uuid5(DEFAULT_NAMESPACE, name),
                    "name": name,
                    "namespace": DEFAULT_NAMESPACE,
                    "owner": owner,
                    "status": status,
                    "metadata": {"crtime": 0, "mtime": 0},
                    "configuration": configuration or {},
                }
            )
        )
        campaign_id = campaign["id"]
        self.campaigns[campaign_id] = campaign
        self.edges[campaign_id] = []

        chain = [self.add_node(campaign_id, "START", kind="start", status=start_status)]
        chain.extend(
            self.add_node(campaign_id, node_name, status=node_status)
            for node_name, node_status in nodes.items()
        )
        chain.append(self.add_node(campaign_id, "END", kind="end"))
        for source, target in zip(chain, chain[1:]):
            self.edges[campaign_id].append((source["id"], target["id"]))
        return campaign

    def add_node(
        self,
        campaign_id: str,
        name: str,
        *,
        kind: str = "step",
        status: str = "waiting",
        version: int = 1,
        configuration: dict | None = None,
    ) -> dict:
        """Add a node to a campaign. The node is not connected to the campaign
        graph unless it is also added to the campaign's edges.
        """
        node = _dump(
            Node.model_validate(
                {
                    "name": name,
                    "namespace": UUID(campaign_id),
                    "version": version,
                    "kind": kind,
                    "status": status,
                    "metadata": {"crtime": 0, "mtime": 0},
                    "configuration": configuration or {},
                }
            )
        )
        self.nodes[node["id"]] = node
        return node

    def expand_step(
        self,
        campaign_id: str,
        step_name: str,
        *,
        groups: Iterable[str],
        collect_status: str = "waiting",
        group_configuration: Callable[[str], dict] | None = None,
    ) -> list[dict]:
        """Expand a step node into its subgraph, as the step does when it is
        prepared: one group node per given group status, numbered from 001,
        each between the step and a ``collect_groups`` node that is connected
        to the step's former successors.

        If given, the group configuration function provides each group's
        configuration from its name. Returns the new group nodes followed by
        the collect node.
        """
        step = next(
            n for n in self.nodes.values() if n["namespace"] == campaign_id and n["name"] == step_name
        )
        group_names = [f"{step_name}_group_{n:03d}" for n, _ in enumerate(groups, start=1)]
        group_nodes = [
            self.add_node(
                campaign_id,
                name,
                kind="group",
                status=group_status,
                configuration=group_configuration(name) if group_configuration else None,
            )
            for name, group_status in zip(group_names, groups)
        ]
        collect = self.add_node(
            campaign_id, f"{step_name}_collect_groups", kind="collect_groups", status=collect_status
        )

        edges = self.edges[campaign_id]
        successors = [target for source, target in edges if source == step["id"]]
        edges[:] = [(source, target) for source, target in edges if source != step["id"]]
        edges.extend((step["id"], group["id"]) for group in group_nodes)
        edges.extend((group["id"], collect["id"]) for group in group_nodes)
        edges.extend((collect["id"], successor) for successor in successors)
        return [*group_nodes, collect]

    def collapse_step(self, campaign_id: str, step_name: str) -> None:
        """Remove a step's subgraph, as the step does when it is unprepared,
        e.g., by a reset: its group and collect nodes are deleted, and the step
        is connected to the collect node's former successors.
        """
        nodes = {n["name"]: n for n in self.nodes.values() if n["namespace"] == campaign_id}
        step, collect = nodes[step_name], nodes[f"{step_name}_collect_groups"]
        removed = {collect["id"]} | {
            n["id"] for name, n in nodes.items() if name.startswith(f"{step_name}_group_")
        }

        edges = self.edges[campaign_id]
        successors = [target for source, target in edges if source == collect["id"]]
        edges[:] = [(s, t) for s, t in edges if s not in removed and t not in removed]
        edges.extend((step["id"], successor) for successor in successors)
        for node_id in removed:
            del self.nodes[node_id]

    def add_log(
        self,
        campaign_id: str,
        *,
        from_status: str,
        to_status: str,
        node_id: str | None = None,
        operator: str = "testuser",
        detail: dict | None = None,
        request_id: str | None = None,
        created_at: datetime | None = None,
        finished_at: datetime | None = None,
        notification_labels: list[str] | None = None,
    ) -> dict:
        """Add a finished activity log entry for a campaign or one of its
        nodes. A request id associates the entry with the client request that
        caused the activity; activity initiated by the daemon has none. The
        entry is created and finished now unless otherwise given.
        """
        now = datetime.now(UTC)
        log = _dump(
            ActivityLog.model_validate(
                {
                    "namespace": campaign_id,
                    "node": node_id,
                    "operator": operator,
                    "created_at": created_at or now,
                    "finished_at": finished_at or now,
                    "from_status": from_status,
                    "to_status": to_status,
                    "detail": detail or {},
                    "metadata": {"request_id": request_id},
                    "notification_labels": notification_labels or ["default"],
                }
            )
        )
        self.logs.append(log)
        return log

    def add_manifest(
        self,
        kind: str,
        name: str,
        *,
        namespace: str | UUID = DEFAULT_NAMESPACE,
        spec: dict | None = None,
        version: int = 1,
        default: bool = False,
    ) -> dict:
        """Add a manifest, by default a library manifest in the default
        namespace.
        """
        manifest = _dump(
            Manifest.model_validate(
                {
                    "id": uuid5(UUID(str(namespace)), f"{kind}.{name}.{version}"),
                    "name": name,
                    "namespace": namespace,
                    "kind": kind,
                    "version": version,
                    "metadata": {"crtime": 0, "mtime": 0},
                    "spec": spec or {},
                    "default": default,
                }
            )
        )
        self.manifests[manifest["id"]] = manifest
        return manifest

    # -- route handlers --------------------------------------------------- #

    def _register_routes(self) -> None:
        r = self.router
        campaign = r"/campaigns/(?P<campaign_id>[^/]+)"
        r.get("/campaigns/", name="campaigns").mock(side_effect=self._campaign_collection)
        r.get(path__regex=rf"{campaign}$", name="campaign").mock(side_effect=self._campaign)
        r.get(path__regex=rf"{campaign}/summary$", name="campaign_summary").mock(side_effect=self._summary)
        r.get(path__regex=rf"{campaign}/nodes$", name="campaign_nodes").mock(side_effect=self._campaign_nodes)
        r.get(path__regex=rf"{campaign}/manifests$", name="campaign_manifests").mock(
            side_effect=self._campaign_manifests
        )
        r.get(path__regex=rf"{campaign}/graph$", name="campaign_graph").mock(side_effect=self._graph)
        r.get(path__regex=rf"{campaign}/logs$", name="campaign_logs").mock(side_effect=self._campaign_logs)
        r.get(
            path__regex=rf"{campaign}/manifest/(?P<kind>[^/]+)(?P<rest>(/[^/]+)*)$",
            name="campaign_manifest",
        ).mock(side_effect=self._campaign_manifest)
        r.get(path__regex=r"/manifests/(?P<manifest_id>[^/]+)$", name="manifest").mock(
            side_effect=self._manifest
        )
        r.route(method__in=["GET", "HEAD"], path__regex=r"/nodes/(?P<node_id>[^/]+)$", name="node").mock(
            side_effect=self._node
        )
        r.get("/logs/", name="logs").mock(side_effect=self._logs)
        r.get("/notifications/", name="notifications").mock(
            side_effect=lambda request: Response(codes.OK, json=self.notifications)
        )
        r.get("/schedules/", name="schedules").mock(
            side_effect=lambda request: Response(codes.OK, json=self.schedules)
        )

    @staticmethod
    def _not_found() -> Response:
        return Response(codes.NOT_FOUND, json={"detail": "Not found"})

    def _find_campaign(self, campaign_id: str) -> dict | None:
        """Find a campaign by its id or name, like the API does."""
        if campaign_id in self.campaigns:
            return self.campaigns[campaign_id]
        return next((c for c in self.campaigns.values() if c["name"] == campaign_id), None)

    def _campaign_nodes_list(self, campaign_id: str) -> list[dict]:
        return [n for n in self.nodes.values() if n["namespace"] == campaign_id]

    def _campaign_collection(self, request: Request) -> Response:
        return Response(codes.OK, json=list(self.campaigns.values()))

    def _campaign(self, request: Request, campaign_id: str) -> Response:
        if (campaign := self._find_campaign(campaign_id)) is None:
            return self._not_found()
        url = f"{API_BASE_URL}/campaigns/{campaign['id']}"
        headers = {
            "Self": url,
            "Nodes": f"{url}/nodes",
            "Edges": f"{url}/edges",
            "Manifests": f"{url}/manifests",
            "Graph": f"{url}/graph",
            "Logs": f"{url}/logs",
        }
        return Response(codes.OK, json=campaign, headers=headers)

    def _summary(self, request: Request, campaign_id: str) -> Response:
        if (campaign := self._find_campaign(campaign_id)) is None:
            return self._not_found()
        counts: dict[str, int] = {}
        for node in self._campaign_nodes_list(campaign["id"]):
            counts[node["status"]] = counts.get(node["status"], 0) + 1
        summary = CampaignSummary.model_validate(
            {
                **campaign,
                "node_summary": [
                    {"status": status, "count": count, "mtime": None} for status, count in counts.items()
                ],
            }
        )
        return Response(codes.OK, json=_dump(summary))

    def _campaign_nodes(self, request: Request, campaign_id: str) -> Response:
        """Paginated node collection, which always provides a "Next" link."""
        if (campaign := self._find_campaign(campaign_id)) is None:
            return self._not_found()
        offset = int(request.url.params.get("offset", 0))
        limit = int(request.url.params.get("limit", 10))
        nodes = self._campaign_nodes_list(campaign["id"])[offset : offset + limit]
        next_url = request.url.copy_merge_params({"offset": offset + limit, "limit": limit})
        return Response(codes.OK, json=nodes, headers={"Next": str(next_url)})

    def _campaign_manifests(self, request: Request, campaign_id: str) -> Response:
        if (campaign := self._find_campaign(campaign_id)) is None:
            return self._not_found()
        manifests = [m for m in self.manifests.values() if m["namespace"] == campaign["id"]]
        return Response(codes.OK, json=manifests)

    def _graph(self, request: Request, campaign_id: str) -> Response:
        """Campaign graph in node-link format with the API's "simple" node
        view.
        """
        if (campaign := self._find_campaign(campaign_id)) is None:
            return self._not_found()
        g: nx.DiGraph = nx.DiGraph()
        for source, target in self.edges.get(campaign["id"], []):
            for node_id in (source, target):
                node = self.nodes[node_id]
                g.add_node(
                    f"{node['name']}.{node['version']}",
                    uuid=node["id"],
                    name=node["name"],
                    status=node["status"],
                    kind=node["kind"],
                    version=node["version"],
                )
            g.add_edge(
                f"{self.nodes[source]['name']}.{self.nodes[source]['version']}",
                f"{self.nodes[target]['name']}.{self.nodes[target]['version']}",
            )
        return Response(codes.OK, json=graph_to_dict(g))

    def _campaign_logs(self, request: Request, campaign_id: str) -> Response:
        """Campaign activity log, optionally constrained to the entries for a
        client request with a ``?request-id=...`` query param.
        """
        if (campaign := self._find_campaign(campaign_id)) is None:
            return self._not_found()
        logs = [log for log in self.logs if log.get("namespace") == campaign["id"]]
        if (request_id := request.url.params.get("request-id")) is not None:
            logs = [log for log in logs if log["metadata"].get("request_id") == request_id]
        return Response(codes.OK, json=logs)

    def _campaign_manifest(self, request: Request, campaign_id: str, kind: str, rest: str) -> Response:
        """Manifest lookup by kind, optionally followed by ``/default`` or by
        ``/{name}[/{version}]``, returning the latest matching version.
        """
        # Library manifests live in the default namespace, which is not one of
        # the fake's campaigns.
        campaign = self._find_campaign(campaign_id)
        namespace = campaign["id"] if campaign is not None else campaign_id
        candidates = [m for m in self.manifests.values() if m["namespace"] == namespace and m["kind"] == kind]
        match rest.strip("/").split("/"):
            case [""]:
                pass
            case ["default"]:
                candidates = [m for m in candidates if m["default"]]
            case [name]:
                candidates = [m for m in candidates if m["name"] == name]
            case [name, version]:
                candidates = [m for m in candidates if m["name"] == name and str(m["version"]) == version]
        if not candidates:
            return self._not_found()
        return Response(codes.OK, json=max(candidates, key=lambda m: m["version"]))

    def _manifest(self, request: Request, manifest_id: str) -> Response:
        if (manifest := self.manifests.get(manifest_id)) is None:
            return self._not_found()
        return Response(codes.OK, json=manifest)

    def _node(self, request: Request, node_id: str) -> Response:
        """Find a node by its id or, given a campaign-id, by its name and
        optional version, otherwise its latest version. A HEAD request also
        describes the node's latest version.
        """
        if (node := self.nodes.get(node_id)) is None:
            campaign_id = request.url.params.get("campaign-id")
            versions = [
                n for n in self.nodes.values() if n["name"] == node_id and n["namespace"] == campaign_id
            ]
            if (version := request.url.params.get("version")) is not None:
                versions = [n for n in versions if str(n["version"]) == version]
            node = max(versions, key=lambda n: n["version"], default=None)
        if node is None:
            return self._not_found()

        headers = {
            "Self": f"{API_BASE_URL}/nodes/{node['id']}",
            "Version": str(node["version"]),
            "Campaign": f"{API_BASE_URL}/campaigns/{node['namespace']}",
        }
        if request.method == "HEAD":
            latest = max(
                n["version"]
                for n in self.nodes.values()
                if n["name"] == node["name"] and n["namespace"] == node["namespace"]
            )
            headers |= {"Latest": str(latest), "Namespace": node["namespace"], "Name": node["name"]}
            return Response(codes.OK, headers=headers)
        return Response(codes.OK, json=node, headers=headers)

    def _logs(self, request: Request) -> Response:
        """Paginated activity log collection, constrained by node, campaign,
        or pilot, and sorted by one or more fields (a ``-`` prefix sorts in
        descending order; null values sort last, or first when descending).
        """
        params = request.url.params
        logs = self.logs
        for param, field in (("node", "node"), ("campaign", "namespace"), ("pilot", "operator")):
            if (value := params.get(param)) is not None:
                logs = [log for log in logs if log[field] == value]

        for field in reversed(params.get("sort", "finished_at").split(",")):
            field = field.strip()
            name = field.removeprefix("-")
            logs = sorted(
                logs,
                key=lambda log: (log[name] is None, log[name] or ""),
                reverse=field.startswith("-"),
            )

        offset = int(params.get("offset", 0))
        limit = int(params.get("limit", 10))
        return Response(codes.OK, json=logs[offset : offset + limit])


@pytest.fixture(scope="session", autouse=True)
def nicegui_storage() -> Generator[Path]:
    """Keep NiceGUI's persistent storage in a temporary directory instead of
    the working directory.
    """
    with (
        TemporaryDirectory(prefix="nicegui-storage-") as storage_dir,
        pytest.MonkeyPatch.context() as mp,
    ):
        storage_path = Path(storage_dir)
        mp.setattr(Storage, "path", storage_path)
        # rebuild app.storage so its persistent dicts pick up the new path
        mp.setattr(app, "storage", Storage())
        yield storage_path


@pytest.fixture(autouse=True)
async def client_factory(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[ClientFactory]:
    """Point the shared cm-web client factory at the fake API.

    The factory's cached client and lock are replaced so that nothing is shared
    between tests, which do not share an event loop.
    """
    kwargs = {**CLIENT_FACTORY._kwargs, "base_url": API_BASE_URL, "headers": {}}
    monkeypatch.setattr(CLIENT_FACTORY, "_kwargs", kwargs)
    monkeypatch.setattr(CLIENT_FACTORY, "_aclient", None)
    monkeypatch.setattr(CLIENT_FACTORY, "_lock", asyncio.Lock())
    yield CLIENT_FACTORY
    await CLIENT_FACTORY.close()


@pytest.fixture
def cm_api() -> Generator[FakeCMService]:
    """A fake CM Service API, initially with no campaigns or manifests."""
    with respx.mock(
        base_url=API_BASE_URL,
        assert_all_mocked=True,
        assert_all_called=False,
        using="httpcore2",
    ) as router:
        yield FakeCMService(router)


@pytest.fixture
def fixture_campaigns(cm_api: FakeCMService) -> list[dict]:
    """Seeds the fake API with five campaigns in a range of campaign statuses,
    with a variety of node statuses. Three campaigns are owned by "weyland"
    and two by "yutani". A campaign is never "waiting"; a new campaign is
    "paused". A campaign does not itself fail when one of its nodes fails, but
    remains "running", as covenant does.

    Covenant is the most realistic of the campaigns: its START node is
    accepted, and its first step has been expanded into a completed subgraph,
    i.e., START -> daniels -> daniels_group_001 -> daniels_collect_groups ->
    walter -> END. Its walter step failed to prepare, before creating its own
    subgraph, which is recorded in walter's activity log.

    Sulaco is similarly realistic: its START node is accepted and its first
    step, hicks, has been expanded into a completed two-group subgraph. Its
    hudson step was prepared, expanding into a subgraph of two waiting groups
    and a waiting collect node, and started, then failed when the check for
    its finish found its HTCondor job had terminated abnormally, all of which
    is recorded in hudson's activity log. The campaign has since been paused.
    """
    campaigns = [
        cm_api.add_campaign(
            "nostromo",
            nodes={"ripley": "accepted", "dallas": "running", "kane": "waiting"},
            status="running",
            owner="weyland",
        ),
        sulaco := cm_api.add_campaign(
            "sulaco",
            nodes={"hicks": "accepted", "hudson": "failed"},
            status="paused",
            start_status="accepted",
            owner="yutani",
        ),
        cm_api.add_campaign(
            "auriga",
            nodes={"call": "waiting", "vriess": "waiting"},
            status="paused",
            owner="yutani",
        ),
        cm_api.add_campaign(
            "narcissus",
            nodes={"jones": "accepted"},
            status="accepted",
            owner="weyland",
        ),
        covenant := cm_api.add_campaign(
            "covenant",
            nodes={"daniels": "accepted", "walter": "failed"},
            status="running",
            start_status="accepted",
            owner="weyland",
        ),
    ]
    cm_api.expand_step(covenant["id"], "daniels", groups=["accepted"], collect_status="accepted")

    # walter failed to prepare, i.e., in its transition from waiting to ready,
    # and the daemon's error handler moved it to failed.
    walter = next(
        n for n in cm_api.nodes.values() if n["namespace"] == covenant["id"] and n["name"] == "walter"
    )
    cm_api.add_log(
        covenant["id"],
        node_id=walter["id"],
        operator="daemon",
        from_status="waiting",
        to_status="failed",
        detail={
            "trigger": "prepare",
            "error": WALTER_PREPARE_ERROR,
            "exception": "RuntimeError",
        },
        created_at=datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC),
        finished_at=datetime(2026, 11, 1, 12, 0, 2, tzinfo=UTC),
    )

    # hudson failed while running: it was prepared (waiting -> ready) and
    # started (ready -> running), but the check for its finish (running ->
    # accepted) found that its HTCondor job had terminated abnormally. Having
    # prepared, hudson has expanded into a subgraph of waiting nodes and has an
    # artifact path; its other side effects of preparing are not mocked.
    cm_api.expand_step(
        sulaco["id"],
        "hicks",
        groups=["accepted", "accepted"],
        collect_status="accepted",
        group_configuration=sulaco_group_configuration,
    )
    cm_api.expand_step(
        sulaco["id"],
        "hudson",
        groups=["waiting", "waiting"],
        collect_status="waiting",
        group_configuration=sulaco_group_configuration,
    )
    hudson = next(
        n for n in cm_api.nodes.values() if n["namespace"] == sulaco["id"] and n["name"] == "hudson"
    )
    # the artifact path is recorded when the node prepares, and the launcher
    # metadata by each check of the running node
    hudson["metadata"]["artifact_path"] = HUDSON_ARTIFACT_PATH
    hudson["metadata"]["launcher"] = {
        "timestamp": int(datetime(2026, 11, 1, 14, 5, tzinfo=UTC).timestamp()),
        "job_id": 8675309,
        "execute_host": "slot1@sdfiana042.sdf.slac.stanford.edu",
    }
    for trigger, from_status, to_status, minute, detail in (
        ("prepare", "waiting", "ready", 0, {}),
        ("start", "ready", "running", 1, {}),
        (
            "finish",
            "running",
            "failed",
            30,
            {"trigger": "finish", "error": HUDSON_FINISH_ERROR, "exception": "RuntimeError"},
        ),
    ):
        cm_api.add_log(
            sulaco["id"],
            node_id=hudson["id"],
            operator="daemon",
            from_status=from_status,
            to_status=to_status,
            detail=detail,
            created_at=datetime(2026, 11, 1, 14, minute, 0, tzinfo=UTC),
            finished_at=datetime(2026, 11, 1, 14, minute, 2, tzinfo=UTC),
        )
    return campaigns


@pytest.fixture
async def user(cm_api: FakeCMService, caplog: pytest.LogCaptureFixture) -> AsyncGenerator[User]:
    """A simulated NiceGUI user of the cm-web application, backed by the fake
    API. The test fails if the application logs any errors.
    """
    async with user_simulation(main_file=MAIN_FILE) as user:
        yield user

    if errors := [r for r in caplog.get_records("call") if r.levelno >= logging.ERROR]:
        pytest.fail(f"There were unexpected ERROR logs: {[r.getMessage() for r in errors]}", pytrace=False)


@pytest.fixture
async def create_user(user: User) -> AsyncGenerator[Callable[[str | None], User]]:
    """A factory for additional simulated users of the same application as the
    `user` fixture.

    Each user has its own browser session, and so its own NiceGUI user
    storage, and identifies itself with the given username in the auth header
    the application expects from its ingress. A username of `None` is an
    anonymous user.
    """
    clients: list[httpx.AsyncClient] = []

    def _create_user(username: str | None) -> User:
        client = httpx.AsyncClient(transport=httpx.ASGITransport(core.app), base_url="http://test")
        if username is not None:
            client.headers[AUTH_HEADER] = username
        clients.append(client)
        return User(client)

    yield _create_user
    for client in clients:
        await client.aclose()


@pytest.fixture
def covenant(fixture_campaigns: list[dict]) -> dict:
    return next(c for c in fixture_campaigns if c["name"] == "covenant")


@pytest.fixture
def walter(cm_api: FakeCMService, covenant: dict) -> dict:
    """The failed step of the covenant campaign."""
    return next(
        n for n in cm_api.nodes.values() if n["namespace"] == covenant["id"] and n["name"] == "walter"
    )


@pytest.fixture
def hudson(cm_api: FakeCMService, fixture_campaigns: list[dict]) -> dict:
    """The failed step of the sulaco campaign, which failed while running."""
    sulaco = next(c for c in fixture_campaigns if c["name"] == "sulaco")
    return next(n for n in cm_api.nodes.values() if n["namespace"] == sulaco["id"] and n["name"] == "hudson")


@pytest.fixture
def fast_activity_polling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shorten the wait between the application's polls of an activity log for
    the result of a request.
    """
    original_sleep = asyncio.sleep
    monkeypatch.setattr(activity, "sleep", lambda _: original_sleep(0.05))
