"""Tests for the steps a user takes to recover a campaign from a failed node,
using the covenant fixture campaign, whose walter step failed to prepare, and
the sulaco fixture campaign, whose hudson step failed while running.
"""

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

import pytest
from nicegui import app, ui
from nicegui.testing.user import User

from .conftest import HUDSON_ARTIFACT_PATH, HUDSON_FINISH_ERROR, FakeCMService, sulaco_group_configuration
from .interactions import (
    campaign_switch,
    choose_recovery_action,
    click,
    eventually,
    follow_link,
    node_cards,
    notifications,
    open_campaign,
    open_dialogs,
    open_node,
    open_recovery_dialog,
    step_forward_chip,
    timeline,
    trigger,
    wait_for_navigation,
)
from .mocks import NodeProcessRpc, NodeStatusChange, Transition, mock_campaign_status_change


async def pause_campaign(user: User, campaign: dict) -> ui.notification:
    """Pause a running campaign with the status card switch and return the
    notification of the pause once it is complete.
    """
    switch = campaign_switch(user)
    assert (switch.value, switch.enabled) == (True, True)
    click(user, switch)
    assert switch.value is False

    notification = (await eventually(lambda: notifications(user), lambda n: len(n) == 1))[0]
    await eventually(lambda: notification.message, lambda m: m.endswith("is now paused"))
    return notification


async def test_pause_campaign(user: User, cm_api: FakeCMService, covenant: dict) -> None:
    """Pausing the campaign creates a notification with a spinner, which is
    updated when the campaign status change is complete.
    """
    patch_route = mock_campaign_status_change(cm_api, covenant)
    await open_campaign(user, covenant)

    switch = campaign_switch(user)
    assert (switch.value, switch.enabled) == (True, True)
    click(user, switch)

    # the notification is dynamic: it shows a spinner while the status change
    # is in progress...
    notification = (await eventually(lambda: notifications(user), lambda n: len(n) == 1))[0]
    await eventually(lambda: notification.spinner, bool)
    assert notification.message == "Pausing campaign covenant"
    # the notification is created without a timeout, i.e., it is persistent
    assert notification.timeout == 0

    # ...and is updated with the result when it is complete
    await eventually(lambda: notification.spinner, lambda spinning: not spinning)
    assert notification.message == "covenant is now paused"
    assert notification.color == "positive"
    assert notification.close_button

    assert patch_route.call_count == 1
    request = patch_route.calls.last.request
    assert json.loads(request.content) == {"status": "paused"}
    assert request.headers["Content-Type"] == "application/merge-patch+json"
    assert cm_api.campaigns[covenant["id"]]["status"] == "paused"
    with user:
        assert app.storage.client["state"].campaigns[covenant["id"]]["status"] == "paused"

    # the refreshed page shows the campaign is paused
    await open_campaign(user, covenant)
    switch = campaign_switch(user)
    assert (switch.value, switch.enabled) == (False, True)


@pytest.mark.parametrize("via", ["avatar", "name", "graph"])
async def test_navigate_to_failed_node(
    user: User,
    cm_api: FakeCMService,
    covenant: dict,
    walter: dict,
    via: Literal["avatar", "name", "graph"],
) -> None:
    """After pausing the campaign, the user navigates to the failed node's
    detail page from its card or from its node in the campaign graph.
    """
    mock_campaign_status_change(cm_api, covenant)
    await open_campaign(user, covenant)
    await pause_campaign(user, covenant)

    node_path = f"/node/{walter['id']}"
    card = node_cards(user)["walter"]
    links = [e for e in card.descendants() if isinstance(e, ui.link)]
    match via:
        case "avatar":
            link = next(link for link in links if any(isinstance(e, ui.avatar) for e in link.descendants()))
            await follow_link(user, link)
        case "name":
            link = next(link for link in links if any(type(e) is ui.label for e in link.descendants()))
            await follow_link(user, link)
        case "graph":
            # clicking a mermaid graph node emits a global "node_click" event
            # with the node's id
            assert user.client is not None
            trigger(user, user.client.layout, "node_click", walter["id"])
            await wait_for_navigation(user, node_path)

    assert user.back_history[-1] == node_path
    await user.should_see("Node Detail", retries=20)
    await user.should_see(kind=ui.label, content="walter")
    await user.should_see(kind=ui.label, content="v1")
    await user.should_see(kind=ui.chip, content="failed")
    # a failed node offers recovery
    await user.should_see(kind=ui.chip, content="recover")


async def test_failed_node_timeline(user: User, cm_api: FakeCMService, walter: dict) -> None:
    """The failed node's detail page has a timeline of its activity, newest
    first: its failure to prepare, after its creation.
    """
    await user.open(f"/node/{walter['id']}")
    # timeline entry titles are properties, not content the user can "see"
    await user.should_see(kind=ui.timeline_entry, retries=20)

    entries = user.find(kind=ui.timeline_entry).elements
    assert [(e.props["title"], e.props["subtitle"]) for e in sorted(entries, key=lambda e: e.id)] == [
        ("walter failed to prepare", "2026-11-01T12:00:02Z"),
        ("walter Created", "1970-01-01T00:00:00Z"),
    ]
    failure = min(entries, key=lambda e: e.id)
    assert failure.props["color"] == "negative"
    assert failure.props["icon"] == "error_outline"
    body = next(e for e in failure.descendants() if isinstance(e, ui.markdown)).content
    assert "**RuntimeError** : Unspecified run-time error." in body
    assert "Predecessor collect step has no output collection" in body

    # the timeline is the node's activity log, newest first
    request = cm_api.router.routes["logs"].calls.last.request
    assert dict(request.url.params) == {"node": walter["id"], "sort": "-finished_at"}


async def test_failed_step_recovery_options(
    user: User, cm_api: FakeCMService, covenant: dict, walter: dict
) -> None:
    """The recovery dialog for a failed step offers to reset or accept the
    step, or to cancel; a step cannot be restarted or rescued, as only a group
    can. Whether the step may be retried is tested separately.
    """
    cm_api.campaigns[covenant["id"]]["status"] = "paused"
    dialog = await open_recovery_dialog(user, walter)

    descendants = list(dialog.descendants())
    assert [e.text for e in descendants if type(e) is ui.label] == ["Recover a failed node"]
    chips = [e.text for e in descendants if isinstance(e, ui.chip)]
    assert "reset" in chips
    assert not {"restart", "rescue"} & set(chips)
    assert [e.text for e in descendants if isinstance(e, ui.button)] == ["accept", "cancel"]

    # cancelling closes the dialog without any recovery action
    with user.scope(kind=ui.dialog):
        user.find(kind=ui.button, content="cancel").click()
    await eventually(lambda: open_dialogs(user), lambda d: not d)
    assert not [call for call in cm_api.router.calls if call.request.method not in ("GET", "HEAD")]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "NodeRecoveryPopup.click offers 'retry' to any failed non-breakpoint node, but retry "
        "transitions a node from failed to ready, which is meaningless for a node that failed "
        "to prepare and so never entered the ready state, as its activity log shows."
    ),
)
async def test_no_retry_for_node_that_never_became_ready(
    user: User, cm_api: FakeCMService, covenant: dict, walter: dict
) -> None:
    """A node that failed before it was ever "ready" cannot be retried."""
    walter_logs = [log for log in cm_api.logs if log["node"] == walter["id"]]
    assert not [log for log in walter_logs if log["to_status"] == "ready"]
    assert [log["detail"]["trigger"] for log in walter_logs] == ["prepare"]

    cm_api.campaigns[covenant["id"]]["status"] = "paused"
    dialog = await open_recovery_dialog(user, walter)
    assert "retry" not in [e.text for e in dialog.descendants() if isinstance(e, ui.chip)]


async def test_runtime_failure_timeline(user: User, hudson: dict) -> None:
    """The timeline of a step that failed while running shows it becoming
    ready and running, then failing to finish, newest first.
    """
    await user.open(f"/node/{hudson['id']}")
    await user.should_see(kind=ui.timeline_entry, retries=20)

    entries = sorted(user.find(kind=ui.timeline_entry).elements, key=lambda e: e.id)
    assert [(e.props["title"], e.props["subtitle"]) for e in entries] == [
        ("hudson failed to finish", "2026-11-01T14:30:02Z"),
        ("hudson became running", "2026-11-01T14:01:02Z"),
        ("hudson became ready", "2026-11-01T14:00:02Z"),
        ("hudson Created", "1970-01-01T00:00:00Z"),
    ]
    assert [e.props["icon"] for e in entries[:3]] == ["error_outline", "run_circle", "pending_actions"]
    assert [e.props["color"] for e in entries[:3]] == ["negative", "primary", "primary"]

    def body(entry: ui.timeline_entry) -> str:
        return next(e for e in entry.descendants() if isinstance(e, ui.markdown)).content

    assert "Job Abnormally Terminated" in body(entries[0])
    assert body(entries[1]) == "Job `8675309` on launch host `slot1@sdfiana042.sdf.slac.stanford.edu`"
    assert body(entries[2]) == f"`{HUDSON_ARTIFACT_PATH}`"


async def test_runtime_failure_recovery_options(user: User, cm_api: FakeCMService, hudson: dict) -> None:
    """A step that failed while running may be retried, as it has been ready,
    as well as reset or accepted; it cannot be restarted or rescued, as only a
    group can.
    """
    dialog = await open_recovery_dialog(user, hudson)
    descendants = list(dialog.descendants())
    assert [e.text for e in descendants if isinstance(e, ui.chip)] == ["retry", "reset"]
    assert [e.text for e in descendants if isinstance(e, ui.button)] == ["accept", "cancel"]

    with user.scope(kind=ui.dialog):
        user.find(kind=ui.button, content="cancel").click()
    await eventually(lambda: open_dialogs(user), lambda d: not d)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "NodeDetailPage.node_activity_timeline builds the 'became ready' entry body with "
        'f"`{artifact_path}`" or "", where the f-string is never empty, so a node without '
        "an artifact_path shows a literal `None`."
    ),
)
async def test_ready_entry_without_artifact_path(user: User, hudson: dict) -> None:
    del hudson["metadata"]["artifact_path"]
    await user.open(f"/node/{hudson['id']}")
    await user.should_see(kind=ui.timeline_entry, retries=20)
    ready = next(
        e for e in user.find(kind=ui.timeline_entry).elements if e.props["title"] == "hudson became ready"
    )
    assert next(e for e in ready.descendants() if isinstance(e, ui.markdown)).content == ""


@pytest.mark.usefixtures("fast_activity_polling")
async def test_retry_failed_node(
    create_user: Callable[[str | None], User], cm_api: FakeCMService, hudson: dict
) -> None:
    """Retrying a node that failed while running returns it to "ready", which
    adds to its timeline without removing its failure.
    """
    change = NodeStatusChange(cm_api, hudson)
    user = create_user("yutani")
    notification = await choose_recovery_action(user, hudson, "retry")

    # the notification shows a spinner while the API processes the request
    await eventually(lambda: notification.spinner, bool)
    assert notification.message == "Retrying node..."
    assert notification.type == "ongoing"
    assert change.route.call_count == 1
    request = change.route.calls.last.request
    assert json.loads(request.content) == {"status": "ready", "force": False}
    assert request.headers["Content-Type"] == "application/merge-patch+json"
    assert request.headers["X-Auth-Request-User"] == "yutani"
    assert hudson["status"] == "failed"

    # the daemon applies the status change, and the notification reports it
    change.complete(finished_at=datetime(2026, 11, 1, 15, 0, 2, tzinfo=UTC))
    await eventually(lambda: notification.spinner, lambda spinning: not spinning)
    assert (notification.type, notification.message) == ("positive", "Node Recovered")

    # the refreshed page shows the node is ready, and the timeline keeps its
    # history, newest first
    await user.should_see(kind=ui.chip, content="ready", retries=20)
    await eventually(lambda: len(user.find(kind=ui.timeline_entry).elements), lambda n: n == 5)
    entries = sorted(user.find(kind=ui.timeline_entry).elements, key=lambda e: e.id)
    assert [(e.props["title"], e.props["subtitle"]) for e in entries] == [
        ("hudson became ready", "2026-11-01T15:00:02Z"),
        ("hudson failed to finish", "2026-11-01T14:30:02Z"),
        ("hudson became running", "2026-11-01T14:01:02Z"),
        ("hudson became ready", "2026-11-01T14:00:02Z"),
        ("hudson Created", "1970-01-01T00:00:00Z"),
    ]
    retry_log = next(log for log in cm_api.logs if log["finished_at"] == "2026-11-01T15:00:02Z")
    assert (retry_log["from_status"], retry_log["to_status"]) == ("failed", "ready")
    assert retry_log["operator"] == "yutani"


@pytest.mark.usefixtures("fast_activity_polling")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "NodeDetailPage.node_detail_ribbon reads the node from the page model before "
        "node_status_chip fetches the current node, so after a node is recovered the ribbon "
        "still offers to recover it."
    ),
)
async def test_no_recovery_after_retry(
    create_user: Callable[[str | None], User], cm_api: FakeCMService, hudson: dict
) -> None:
    change = NodeStatusChange(cm_api, hudson)
    user = create_user("yutani")
    notification = await choose_recovery_action(user, hudson, "retry")
    await eventually(lambda: notification.spinner, bool)
    change.complete(finished_at=datetime(2026, 11, 1, 15, 0, 2, tzinfo=UTC))
    await eventually(lambda: notification.spinner, lambda spinning: not spinning)

    await user.should_see(kind=ui.chip, content="ready", retries=20)
    await user.should_not_see(kind=ui.chip, content="recover")


@pytest.mark.usefixtures("fast_activity_polling")
async def test_recovery_by_reset(
    create_user: Callable[[str | None], User],
    cm_api: FakeCMService,
    fixture_campaigns: list[dict],
    hudson: dict,
) -> None:
    """After hudson is retried in its paused campaign, the user steps it
    forward to running, then again to failed, as the retry is unsuccessful;
    the user then resets it to waiting, which rolls back its subgraph. The
    user steps it forward again: it prepares, expanding its subgraph again,
    then runs, and is accepted, as the recovery by reset is successful.

    The page is not refreshed by a step forward, so the user reloads it to see
    each step's result.
    """
    sulaco = next(c for c in fixture_campaigns if c["name"] == "sulaco")
    change = NodeStatusChange(cm_api, hudson)
    rpc = NodeProcessRpc(
        cm_api,
        hudson,
        [
            # after the retry
            Transition("running", datetime(2026, 11, 1, 15, 5, 2, tzinfo=UTC)),
            Transition(
                "failed",
                datetime(2026, 11, 1, 15, 35, 2, tzinfo=UTC),
                detail={"trigger": "finish", "error": HUDSON_FINISH_ERROR, "exception": "RuntimeError"},
            ),
            # after the reset
            Transition(
                "ready",
                datetime(2026, 11, 1, 15, 45, 2, tzinfo=UTC),
                side_effect=lambda: cm_api.expand_step(
                    sulaco["id"],
                    "hudson",
                    groups=["waiting", "waiting"],
                    collect_status="waiting",
                    group_configuration=sulaco_group_configuration,
                ),
            ),
            Transition("running", datetime(2026, 11, 1, 15, 46, 2, tzinfo=UTC)),
            Transition("accepted", datetime(2026, 11, 1, 16, 15, 2, tzinfo=UTC)),
        ],
    )
    user = create_user("yutani")

    # hudson is retried, so it is ready, and the step forward control is
    # available and enabled
    notification = await choose_recovery_action(user, hudson, "retry")
    await eventually(lambda: notification.spinner, bool)
    change.complete(finished_at=datetime(2026, 11, 1, 15, 0, 2, tzinfo=UTC))
    await user.should_see(kind=ui.chip, content="ready", retries=20)
    assert (step_forward_chip(user).visible, step_forward_chip(user).enabled) == (True, True)

    # the first step forward starts hudson
    click(user, step_forward_chip(user))
    await eventually(lambda: rpc.route.call_count, lambda n: n == 1)
    assert hudson["status"] == "running"
    await open_node(user, hudson)
    await user.should_see(kind=ui.chip, content="running")
    assert timeline(user)[0] == "hudson became running"
    assert step_forward_chip(user).enabled

    # the second step forward finds hudson failed again
    click(user, step_forward_chip(user))
    await eventually(lambda: rpc.route.call_count, lambda n: n == 2)
    assert hudson["status"] == "failed"
    await open_node(user, hudson)
    await user.should_see(kind=ui.chip, content="failed")
    assert timeline(user)[0] == "hudson failed to finish"
    assert not step_forward_chip(user).enabled

    # the user resets hudson to waiting, which rolls back its subgraph
    notification = await choose_recovery_action(user, hudson, "reset")
    await eventually(lambda: notification.spinner, bool)
    assert notification.message == "Resetting node..."
    request = change.route.calls.last.request
    assert json.loads(request.content) == {"status": "waiting", "force": True}
    change.complete(
        finished_at=datetime(2026, 11, 1, 15, 40, 2, tzinfo=UTC),
        detail={"message": "hudson was rolled back via 'reset'"},
    )
    cm_api.collapse_step(sulaco["id"], "hudson")
    await eventually(lambda: notification.spinner, lambda spinning: not spinning)
    assert (notification.type, notification.message) == ("positive", "Node Recovered")

    await user.should_see(kind=ui.chip, content="waiting", retries=20)
    await eventually(lambda: len(timeline(user)), lambda n: n == 8)
    assert timeline(user) == [
        "hudson became waiting",
        "hudson failed to finish",
        "hudson became running",
        "hudson became ready",
        "hudson failed to finish",
        "hudson became running",
        "hudson became ready",
        "hudson Created",
    ]
    reset_entry = min(user.find(kind=ui.timeline_entry).elements, key=lambda e: e.id)
    body = next(e for e in reset_entry.descendants() if isinstance(e, ui.markdown)).content
    assert body == "hudson was rolled back via 'reset'"

    # the campaign graph no longer has hudson's subgraph
    graph_nodes = {n["name"] for n in cm_api.nodes.values() if n["namespace"] == sulaco["id"]}
    assert not {name for name in graph_nodes if name.startswith("hudson_")}
    names = {n["id"]: n["name"] for n in cm_api.nodes.values()}
    assert ("hudson", "END") in {(names[s], names[t]) for s, t in cm_api.edges[sulaco["id"]]}

    # the user steps hudson forward from waiting to ready, to running, and to
    # accepted, reloading the page after each step
    for n, (status, latest) in enumerate(
        (
            ("ready", "hudson became ready"),
            ("running", "hudson became running"),
            ("accepted", "hudson became accepted"),
        ),
        start=3,
    ):
        assert step_forward_chip(user).enabled
        click(user, step_forward_chip(user))
        await eventually(lambda: rpc.route.call_count, lambda count: count == n)
        assert hudson["status"] == status
        await open_node(user, hudson)
        await user.should_see(kind=ui.chip, content=status)
        assert timeline(user)[0] == latest

    # hudson is accepted, so it can no longer be stepped forward or recovered
    assert not step_forward_chip(user).enabled
    await user.should_not_see(kind=ui.chip, content="recover")
    assert timeline(user) == [
        "hudson became accepted",
        "hudson became running",
        "hudson became ready",
        "hudson became waiting",
        "hudson failed to finish",
        "hudson became running",
        "hudson became ready",
        "hudson failed to finish",
        "hudson became running",
        "hudson became ready",
        "hudson Created",
    ]

    # preparing again expanded hudson's subgraph of waiting nodes
    statuses = {n["name"]: n["status"] for n in cm_api.nodes.values() if n["namespace"] == sulaco["id"]}
    assert {name: status for name, status in statuses.items() if name.startswith("hudson")} == {
        "hudson": "accepted",
        "hudson_group_001": "waiting",
        "hudson_group_002": "waiting",
        "hudson_collect_groups": "waiting",
    }


@pytest.mark.xfail(
    strict=True,
    reason=(
        "NodeDetailPage.node_advance_chip binds its visibility to the campaign status in client "
        "storage, which the node detail page never sets, so the binding never applies and the "
        "step forward control is visible for a node of a campaign that is not paused."
    ),
)
async def test_no_step_forward_for_running_campaign(
    user: User, cm_api: FakeCMService, fixture_campaigns: list[dict]
) -> None:
    """The step forward control is only visible when the node's campaign is
    paused.
    """
    nostromo = next(c for c in fixture_campaigns if c["name"] == "nostromo")
    dallas = next(
        n for n in cm_api.nodes.values() if n["namespace"] == nostromo["id"] and n["name"] == "dallas"
    )
    assert (nostromo["status"], dallas["status"]) == ("running", "running")

    await open_node(user, dallas)
    assert not step_forward_chip(user).visible


@pytest.mark.usefixtures("fast_activity_polling")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "wait_for_activity_to_complete reads the first activity log entry before checking whether "
        "it ran out of time, so when no entry appears it raises IndexError instead of warning "
        "that it timed out."
    ),
)
async def test_recovery_action_times_out(
    create_user: Callable[[str | None], User], cm_api: FakeCMService, hudson: dict
) -> None:
    """When the daemon does not apply a requested status change in time, the
    notification warns that it timed out.
    """
    NodeStatusChange(cm_api, hudson)
    user = create_user("yutani")
    notification = await choose_recovery_action(user, hudson, "retry")
    # the status change is never completed, and the (shortened) polling gives
    # up well within a second
    await eventually(lambda: notification.spinner, bool)
    await asyncio.sleep(1.0)
    assert (notification.type, notification.message) == ("warning", "Timed out waiting for result")
    assert not notification.spinner
