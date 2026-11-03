"""Tests for the sulaco fixture campaign after its hudson step is recovered,
when the campaign is resumed and the daemon evolves hudson's two groups in
parallel: hudson_group_001 succeeds and hudson_group_002 fails while running.
"""

import asyncio
import copy
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import NamedTuple

import pytest
import respx
from httpx import Response, codes
from nicegui import ui
from nicegui.testing.user import User

from .conftest import HUDSON_FINISH_ERROR, HUDSON_GROUP_FINISH_ERROR, STATUS_FILL_COLORS, FakeCMService
from .interactions import (
    campaign_switch,
    click,
    eventually,
    follow_link,
    node_cards,
    notifications,
    open_campaign,
    open_dialogs,
    open_recovery_dialog,
    timeline,
)
from .mocks import (
    GraphInsert,
    NodeCreation,
    NodeStatusChange,
    Transition,
    apply_transition,
    campaign_transition,
    daemon_tick,
    mock_campaign_status_change,
)

GROUP_1_BPS_REPORT = {
    "isr": {"n_succeeded": 189},
    "calibrateImage": {"n_succeeded": 189},
    "finalJob": {"n_succeeded": 1},
}
"""The BPS report of hudson_group_001, whose workflow succeeded."""

GROUP_2_BPS_REPORT = {
    "isr": {"n_succeeded": 189},
    "calibrateImage": {"n_succeeded": 176, "n_failed": 13},
    "finalJob": {"n_pruned": 1},
}
"""The BPS report of hudson_group_002, whose workflow failed."""


def at(hour: int, minute: int) -> datetime:
    return datetime(2026, 11, 1, hour, minute, 2, tzinfo=UTC)


PARALLEL_RUN: list[dict[str, Transition]] = [
    {group: Transition("ready", at(16, 21)) for group in ("hudson_group_001", "hudson_group_002")},
    {
        "hudson_group_001": Transition(
            "running",
            at(16, 22),
            metadata={"launcher": {"job_id": 8675401, "execute_host": "sdfiana043.sdf.slac.stanford.edu"}},
        ),
        "hudson_group_002": Transition(
            "running",
            at(16, 22),
            metadata={"launcher": {"job_id": 8675402, "execute_host": "sdfiana044.sdf.slac.stanford.edu"}},
        ),
    },
    {
        "hudson_group_001": Transition(
            "accepted", at(18, 0), metadata={"bps_report": GROUP_1_BPS_REPORT, "percent_done": 1.0}
        ),
        "hudson_group_002": Transition(
            "failed",
            at(18, 30),
            detail={"trigger": "finish", "error": HUDSON_GROUP_FINISH_ERROR, "exception": "RuntimeError"},
            metadata={"bps_report": GROUP_2_BPS_REPORT, "percent_done": 1.0},
        ),
    },
]
"""The daemon's evolution of hudson's two groups in parallel, by tick: both
prepare and start, then hudson_group_001 is accepted and hudson_group_002 fails
to finish.
"""


HUDSON_RECOVERY: list[Transition] = [
    Transition("ready", at(15, 0)),
    Transition("running", at(15, 5)),
    Transition(
        "failed",
        at(15, 35),
        detail={"trigger": "finish", "error": HUDSON_FINISH_ERROR, "exception": "RuntimeError"},
    ),
    Transition("waiting", at(15, 40), detail={"message": "hudson was rolled back via 'reset'"}),
    Transition("ready", at(15, 45)),
    Transition("running", at(15, 46)),
    Transition("accepted", at(16, 15)),
]
"""hudson's recovery by reset (see `test_failure_recovery.py::
test_recovery_by_reset`): it is retried and stepped forward, fails again, and
is reset and stepped forward until it is accepted.
"""


@pytest.fixture
def sulaco(fixture_campaigns: list[dict]) -> dict:
    return next(c for c in fixture_campaigns if c["name"] == "sulaco")


@pytest.fixture
def recovered_hudson(cm_api: FakeCMService, hudson: dict) -> dict:
    """The hudson step as it is after its recovery by reset (see
    `test_failure_recovery.py::test_recovery_by_reset`): accepted, with a
    subgraph of two waiting groups and a waiting collect node, in its paused
    campaign, and with the history of its recovery in its activity log,
    including its second failure.
    """
    for transition in HUDSON_RECOVERY:
        apply_transition(cm_api, hudson, transition)
    return hudson


@pytest.fixture
def failed_group(cm_api: FakeCMService, sulaco: dict, recovered_hudson: dict) -> dict:
    """hudson_group_002 as it is after the parallel run of hudson's groups in
    the resumed campaign (see `test_parallel_groups`): failed to finish, while
    hudson_group_001 is accepted and the campaign is running.
    """
    sulaco["status"] = "running"
    for tick in PARALLEL_RUN:
        daemon_tick(cm_api, sulaco["id"], tick)
    return next(
        n for n in cm_api.nodes.values() if n["namespace"] == sulaco["id"] and n["name"] == "hudson_group_002"
    )


def graph_fills(user: User) -> dict[str, str]:
    """The fill color of each campaign graph diagram node, by node name."""
    mermaid = user.find(kind=ui.mermaid).elements.pop()
    fills = re.findall(r"^style (\S+)\.\d+ fill:(#[0-9a-f]{6})$", mermaid.content, re.MULTILINE)
    return dict(fills)


def card_statuses(user: User) -> dict[str, str]:
    """The status shown on each node card, by node name."""
    statuses = set(STATUS_FILL_COLORS)
    return {
        name: next(e.text for e in card.descendants() if isinstance(e, ui.chip) and e.text in statuses)
        for name, card in node_cards(user).items()
    }


async def resume_campaign(user: User, campaign: dict) -> None:
    """Resume a paused campaign with the status card switch, waiting for the
    notification that it is running.
    """
    switch = campaign_switch(user)
    assert (switch.value, switch.enabled) == (False, True)
    click(user, switch)
    notification = (await eventually(lambda: notifications(user), lambda n: len(n) == 1))[0]
    assert notification.message == f"Starting campaign {campaign['name']}"
    await eventually(lambda: notification.message, lambda m: m == f"{campaign['name']} is now running")


async def test_parallel_groups(
    create_user: Callable[[str | None], User],
    cm_api: FakeCMService,
    sulaco: dict,
    recovered_hudson: dict,
) -> None:
    """After the user resumes the campaign, the daemon evolves hudson's two
    groups in parallel: both prepare and start, then hudson_group_001 is
    accepted and hudson_group_002 fails to finish. The campaign remains
    running, and the collect node waits for both groups.

    The campaign detail page is not refreshed by the daemon's activity, so the
    user reloads it to see each step's result.
    """
    mock_campaign_status_change(cm_api, sulaco)
    user = create_user("yutani")
    await open_campaign(user, sulaco)
    await resume_campaign(user, sulaco)
    assert sulaco["status"] == "running"

    expected = [("ready", "ready"), ("running", "running"), ("accepted", "failed")]

    for tick, (status_1, status_2) in zip(PARALLEL_RUN, expected):
        daemon_tick(cm_api, sulaco["id"], tick)
        await open_campaign(user, sulaco)
        expected_statuses = {
            "hudson": "accepted",
            "hudson_group_001": status_1,
            "hudson_group_002": status_2,
            "hudson_collect_groups": "waiting",
            "END": "waiting",
        }
        statuses = card_statuses(user)
        assert {name: statuses[name] for name in expected_statuses} == expected_statuses
        fills = graph_fills(user)
        assert {name: fills[name] for name in expected_statuses} == {
            name: STATUS_FILL_COLORS[status] for name, status in expected_statuses.items()
        }

    # the failed group does not fail the campaign, which remains running
    assert sulaco["status"] == "running"
    switch = campaign_switch(user)
    assert (switch.value, switch.enabled) == (True, True)


async def test_failed_group_detail(user: User, sulaco: dict, failed_group: dict) -> None:
    """The failed group's detail page, reached from its node card, has its
    BPS report and a timeline ending with its failure to finish.
    """
    await open_campaign(user, sulaco)
    card = node_cards(user)["hudson_group_002"]
    await follow_link(user, next(e for e in card.descendants() if isinstance(e, ui.link)))
    await user.should_see(kind=ui.timeline_entry, retries=20)

    assert timeline(user) == [
        "hudson_group_002 failed to finish",
        "hudson_group_002 became running",
        "hudson_group_002 became ready",
        "hudson_group_002 Created",
    ]
    failure = min(user.find(kind=ui.timeline_entry).elements, key=lambda e: e.id)
    body = next(e for e in failure.descendants() if isinstance(e, ui.markdown)).content
    assert "WMS Job is Failed" in body

    # the BPS report shows the succeeded share of the workflow's jobs, and a
    # row of job counts by status for each of its tasks
    await user.should_see(kind=ui.markdown, content="### BPS Report")
    progress = user.find(kind=ui.circular_progress).elements.pop()
    assert (progress.value, progress.props["max"]) == (365, 379)
    table = next(t for t in user.find(kind=ui.table).elements if any("task" in row for row in t.rows))
    assert {
        row["task"]: {k: v for k, v in row.items() if k != "task"} for row in table.rows
    } == GROUP_2_BPS_REPORT


RESCUE_RUN: list[Transition] = [
    Transition("ready", at(19, 1)),
    Transition(
        "running",
        at(19, 2),
        metadata={"launcher": {"job_id": 8675403, "execute_host": "sdfiana045.sdf.slac.stanford.edu"}},
    ),
    Transition(
        "accepted",
        at(19, 40),
        metadata={
            "bps_report": {"calibrateImage": {"n_succeeded": 13}, "finalJob": {"n_succeeded": 1}},
            "percent_done": 1.0,
        },
    ),
]
"""The daemon's evolution of the rescue group, whose BPS workflow skips the
quanta that hudson_group_002 produced, and succeeds.
"""


class RescueApi(NamedTuple):
    """The mocks of the API's write operations used by a rescue."""

    campaign_status: respx.Route
    node_creation: NodeCreation
    graph_insert: GraphInsert
    group_acceptance: NodeStatusChange


@pytest.fixture
def rescue_api(cm_api: FakeCMService, sulaco: dict, failed_group: dict) -> RescueApi:
    return RescueApi(
        campaign_status=mock_campaign_status_change(cm_api, sulaco),
        node_creation=NodeCreation(cm_api),
        graph_insert=GraphInsert(cm_api, sulaco),
        group_acceptance=NodeStatusChange(cm_api, failed_group),
    )


def edges_by_name(cm_api: FakeCMService, campaign: dict) -> set[tuple[str, str]]:
    names = {n["id"]: n["name"] for n in cm_api.nodes.values()}
    return {(names[s], names[t]) for s, t in cm_api.edges[campaign["id"]]}


async def start_rescue(user: User, group: dict) -> None:
    """Choose to rescue a failed group in its recovery dialog, and confirm."""
    dialog = await open_recovery_dialog(user, group)
    click(user, next(e for e in dialog.descendants() if isinstance(e, ui.chip) and e.text == "rescue"))
    await user.should_see(kind=ui.button, content="Yes")
    click(user, user.find(kind=ui.button, content="Yes").elements.pop())


@pytest.mark.usefixtures("fast_activity_polling")
async def test_rescue_failed_group(
    create_user: Callable[[str | None], User],
    cm_api: FakeCMService,
    sulaco: dict,
    failed_group: dict,
    rescue_api: RescueApi,
) -> None:
    """Rescuing the failed group pauses the campaign, puts a rescue group
    after it in the graph, configured to skip the failed group's work, and
    force-accepts the failed group. When the user resumes the campaign, the
    daemon processes the rescue group, which succeeds, so that both groups of
    hudson's subgraph are done and its collect node is next.
    """
    user = create_user("yutani")
    group_config = failed_group["configuration"]
    group_run = group_config["butler"]["collections"]["run"]
    group_output = group_config["butler"]["collections"]["group_output"]

    # a failed group may be restarted, retried, reset, rescued, or accepted
    dialog = await open_recovery_dialog(user, failed_group)
    descendants = list(dialog.descendants())
    assert [e.text for e in descendants if isinstance(e, ui.chip)] == ["restart", "retry", "reset", "rescue"]
    assert [e.text for e in descendants if isinstance(e, ui.button)] == ["accept", "cancel"]
    with user.scope(kind=ui.dialog):
        user.find(kind=ui.button, content="cancel").click()
    await eventually(lambda: open_dialogs(user), lambda d: not d)

    await start_rescue(user, failed_group)

    # the rescue pauses the campaign, creates the rescue group and inserts it
    # into the graph, then force-accepts the failed group
    await eventually(lambda: rescue_api.group_acceptance.route.call_count, lambda n: n == 1)
    assert sulaco["status"] == "paused"
    assert rescue_api.node_creation.route.call_count == 1
    assert rescue_api.graph_insert.route.call_count == 1
    assert json.loads(rescue_api.group_acceptance.route.calls.last.request.content) == {
        "status": "accepted",
        "force": True,
    }

    accepting = await eventually(
        lambda: [n for n in notifications(user) if n.message == "Accepting node..."], lambda n: len(n) == 1
    )
    assert accepting[0].spinner
    rescue_api.group_acceptance.complete(finished_at=at(18, 45))
    await eventually(lambda: accepting[0].message, lambda m: m == "Node Recovered")
    assert failed_group["status"] == "accepted"

    # the rescue group is a copy of the failed group, with new collections
    # and an option to skip the quanta already in the failed group's run
    rescue = rescue_api.node_creation.created[0]
    assert (rescue["name"], rescue["kind"], rescue["version"], rescue["status"]) == (
        "hudson_group_002_rescue_1",
        "group",
        1,
        "waiting",
    )
    assert rescue["metadata"]["rescues"] == 1
    assert rescue["configuration"]["butler"]["collections"] == {
        "step_input": group_config["butler"]["collections"]["step_input"],
        "group_output": f"{group_output}/rescue_001",
        "run": f"{group_run}/rescue_001",
    }
    assert rescue["configuration"]["bps"]["extra_qgraph_options"] == [f"--skip-existing-in {group_run}"]
    assert rescue["configuration"]["bps"]["pipeline_yaml"] == group_config["bps"]["pipeline_yaml"]

    # the rescue group is inserted between the failed group and the collect
    # node
    edges = edges_by_name(cm_api, sulaco)
    assert {
        ("hudson_group_002", "hudson_group_002_rescue_1"),
        ("hudson_group_002_rescue_1", "hudson_collect_groups"),
    } <= edges
    assert ("hudson_group_002", "hudson_collect_groups") not in edges

    # the user resumes the campaign, and the daemon processes the rescue
    # group, which follows the happy path
    await open_campaign(user, sulaco)
    await resume_campaign(user, sulaco)
    for transition in RESCUE_RUN:
        daemon_tick(cm_api, sulaco["id"], {"hudson_group_002_rescue_1": transition})
        await open_campaign(user, sulaco)
        assert card_statuses(user)["hudson_group_002_rescue_1"] == transition.to_status
        assert graph_fills(user)["hudson_group_002_rescue_1"] == STATUS_FILL_COLORS[transition.to_status]

    # hudson's groups are done, and its collect node is the next to process
    expected_statuses = {
        "hudson": "accepted",
        "hudson_group_001": "accepted",
        "hudson_group_002": "accepted",
        "hudson_group_002_rescue_1": "accepted",
        "hudson_collect_groups": "waiting",
        "END": "waiting",
    }
    statuses = card_statuses(user)
    assert {name: statuses[name] for name in expected_statuses} == expected_statuses
    collect_predecessors = {s for s, t in edges_by_name(cm_api, sulaco) if t == "hudson_collect_groups"}
    assert collect_predecessors == {"hudson_group_001", "hudson_group_002_rescue_1"}
    assert sulaco["status"] == "running"


@pytest.mark.usefixtures("fast_activity_polling")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "rescue_group continues after insert_or_append_node fails, because that function only "
        "notifies the user of a 409 Conflict instead of raising, so the failed group is "
        "force-accepted without a rescue group in the graph."
    ),
)
async def test_rescue_does_not_accept_group_without_rescue(
    user: User, sulaco: dict, failed_group: dict, rescue_api: RescueApi
) -> None:
    # the graph cannot be modified, e.g., because the campaign is not paused
    rescue_api.graph_insert.route.mock(
        return_value=Response(codes.CONFLICT, json={"detail": "Graph for Campaign cannot be modified."})
    )
    await start_rescue(user, failed_group)
    await eventually(lambda: rescue_api.graph_insert.route.call_count, lambda n: n == 1)
    accepted = False
    for _ in range(10):
        if accepted := rescue_api.group_acceptance.route.called:
            # complete the acceptance at once, so the rescue finishes cleanly
            rescue_api.group_acceptance.complete(finished_at=at(18, 45))
            break
        await asyncio.sleep(0.05)
    assert not accepted


@pytest.mark.usefixtures("fast_activity_polling")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "rescue_group pauses the campaign with toggle_campaign_state given only the campaign "
        "id, so the pause notification has no campaign name, e.g., 'Pausing campaign '."
    ),
)
async def test_rescue_pause_notification(
    user: User, sulaco: dict, failed_group: dict, rescue_api: RescueApi
) -> None:
    await start_rescue(user, failed_group)
    pausing = (await eventually(lambda: notifications(user), lambda n: len(n) == 1))[0]
    assert pausing.message == "Pausing campaign sulaco"
    await eventually(lambda: pausing.message, lambda m: m == "sulaco is now paused")

    await eventually(lambda: rescue_api.group_acceptance.route.call_count, lambda n: n == 1)
    rescue_api.group_acceptance.complete(finished_at=at(18, 45))


@pytest.fixture
def rescued_group(cm_api: FakeCMService, sulaco: dict, failed_group: dict) -> dict:
    """The rescue group of hudson_group_002 as it is after the rescue and the
    resumed campaign's processing of the rescue group (see
    `test_rescue_failed_group`): accepted, between the force-accepted
    hudson_group_002 and hudson's waiting collect node, in the running
    campaign. Returns the rescue group.
    """
    # the rescue pauses the campaign, creates the rescue group, and inserts it
    # after the failed group, which it force-accepts
    campaign_transition(cm_api, sulaco, "paused", at(18, 40), operator="yutani")
    collections = failed_group["configuration"]["butler"]["collections"]
    configuration = copy.deepcopy(failed_group["configuration"])
    configuration["butler"]["collections"] |= {
        "group_output": f"{collections['group_output']}/rescue_001",
        "run": f"{collections['run']}/rescue_001",
    }
    configuration["bps"]["extra_qgraph_options"] = [f"--skip-existing-in {collections['run']}"]
    rescue = cm_api.add_node(
        sulaco["id"], "hudson_group_002_rescue_1", kind="group", configuration=configuration
    )
    rescue["metadata"]["rescues"] = 1
    edges = cm_api.edges[sulaco["id"]]
    successors = [t for s, t in edges if s == failed_group["id"]]
    edges[:] = [(s, t) for s, t in edges if s != failed_group["id"]]
    edges.append((failed_group["id"], rescue["id"]))
    edges.extend((rescue["id"], successor) for successor in successors)
    apply_transition(cm_api, failed_group, Transition("accepted", at(18, 45)))

    # the user resumes the campaign, and the daemon processes the rescue group
    campaign_transition(cm_api, sulaco, "running", at(18, 50), operator="yutani")
    for transition in RESCUE_RUN:
        apply_transition(cm_api, rescue, transition)
    return rescue


def gauge(user: User, label: str) -> ui.circular_progress:
    """The progress element of a campaign detail page status gauge card."""
    for card in user.find(kind=ui.card).elements:
        descendants = list(card.descendants())
        if any(type(e) is ui.label and e.text == label for e in descendants):
            return next(e for e in descendants if isinstance(e, ui.circular_progress))
    msg = f"No {label} gauge"
    raise AssertionError(msg)


async def test_campaign_conclusion(
    create_user: Callable[[str | None], User],
    cm_api: FakeCMService,
    sulaco: dict,
    rescued_group: dict,
) -> None:
    """After the rescue, the daemon processes hudson's collect node and the END
    node, and finishes the campaign: it is accepted, its run switch is off and
    can no longer be turned on, and its Errors gauge counts every failure
    during its execution, although each was recovered.
    """
    campaign_status = mock_campaign_status_change(cm_api, sulaco)
    user = create_user("yutani")

    for node in ("hudson_collect_groups", "END"):
        for to_status, minute in (("ready", 1), ("running", 2), ("accepted", 10)):
            hour = 20 if node == "hudson_collect_groups" else 21
            daemon_tick(cm_api, sulaco["id"], {node: Transition(to_status, at(hour, minute))})
            await open_campaign(user, sulaco)
            assert card_statuses(user)[node] == to_status
            assert sulaco["status"] == "running"

    # the daemon finishes the campaign once its END node is accepted
    campaign_transition(cm_api, sulaco, "accepted", at(21, 11))
    await open_campaign(user, sulaco)
    nodes = [n for n in cm_api.nodes.values() if n["namespace"] == sulaco["id"]]
    assert {n["status"] for n in nodes} == {"accepted"}
    assert set(graph_fills(user).values()) == {STATUS_FILL_COLORS["accepted"]}

    # the run switch is off, and turning it on does nothing
    switch = campaign_switch(user)
    assert (switch.value, switch.enabled) == (False, False)
    click(user, switch)
    assert switch.value is False
    await asyncio.sleep(0.2)
    assert not campaign_status.called

    # the Nodes gauge is full, and the Errors gauge counts hudson's two
    # failures and hudson_group_002's failure among all the activity
    nodes_gauge = gauge(user, "Nodes")
    assert (nodes_gauge.value, nodes_gauge.props["max"]) == (len(nodes), len(nodes))
    logs = [log for log in cm_api.logs if log["namespace"] == sulaco["id"]]
    failures = [log for log in logs if log["detail"].get("error")]
    assert [cm_api.nodes[log["node"]]["name"] for log in failures] == ["hudson", "hudson", "hudson_group_002"]
    errors_gauge = gauge(user, "Errors")
    assert (errors_gauge.value, errors_gauge.props["max"]) == (3, len(logs))

    # the campaign's overview card shows it is accepted, and its switch is
    # disabled too
    await user.open("/")
    await user.should_see("sulaco")
    card_switch = user.find(kind=ui.switch, content="accepted").elements.pop()
    assert (card_switch.value, card_switch.enabled) == (False, False)
