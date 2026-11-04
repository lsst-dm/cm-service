"""Tests for the Schedule Overview page."""

import json

import pytest

# FIXME refactor with httpx2 when respx (or a replacement) supports it
from httpx import Response, codes
from nicegui import ui
from nicegui.testing.user import User

from .conftest import FakeCMService
from .interactions import eventually, open_dialogs, trigger


async def open_schedule_overview(user: User) -> None:
    await user.open("/schedules")
    await user.should_see(kind=ui.table, retries=30)


def emit_schedule_action(user: User, schedule: dict, action: str) -> None:
    """Emit a schedule table row action, as the browser does when the user
    clicks the row's control for the action.
    """
    assert user.client is not None
    element = next(
        e
        for e in user.client.layout.descendants()
        for listener in e._event_listeners.values()
        if listener.js_handler is not None and f"'{action}'" in listener.js_handler
    )
    trigger(user, element, "click", [schedule["id"], action])


def schedule_row(user: User) -> dict:
    """The schedule table's only row."""
    (table,) = user.find(kind=ui.table).elements
    (row,) = table.rows
    return row


@pytest.mark.xfail(
    strict=True,
    reason=(
        "The toggle action changes the page's enabled state before it patches the schedule, "
        "and keeps the change when the patch fails, so the next toggle sends the wrong state."
    ),
)
async def test_failed_toggle_keeps_enabled_state(user: User, cm_api: FakeCMService) -> None:
    schedule = cm_api.add_schedule("nightly", configuration={"name_format": "%Y%m%d"})
    patch = cm_api.router.patch(f"/schedules/{schedule['id']}").mock(
        side_effect=[Response(codes.INTERNAL_SERVER_ERROR), Response(codes.OK)]
    )
    await open_schedule_overview(user)

    # Enabling the schedule fails, so the schedule is still disabled
    emit_schedule_action(user, schedule, "toggle")
    await eventually(lambda: patch.call_count, lambda n: n == 1)

    # Toggling the schedule again tries to enable it again
    emit_schedule_action(user, schedule, "toggle")
    await eventually(lambda: patch.call_count, lambda n: n == 2)
    assert json.loads(patch.calls[1].request.content) == {"is_enabled": True}


@pytest.mark.xfail(
    strict=True,
    reason=(
        "The cron action changes the page's cron before it patches the schedule, and keeps the "
        "change when the patch fails, so the page shows a cron the schedule does not have."
    ),
)
async def test_failed_cron_change_keeps_cron(user: User, cm_api: FakeCMService) -> None:
    schedule = cm_api.add_schedule("monthly", cron="0 0 1 * *", configuration={"name_format": "%Y%m%d"})
    patch = cm_api.router.patch(f"/schedules/{schedule['id']}").mock(
        side_effect=[Response(codes.INTERNAL_SERVER_ERROR), Response(codes.OK)]
    )
    await open_schedule_overview(user)

    # Changing the schedule's cron fails, so the schedule keeps its cron
    emit_schedule_action(user, schedule, "cron")
    (cron_dialog,) = await eventually(lambda: open_dialogs(user), lambda d: len(d) == 1)
    cron_dialog.submit("30 6 * * *")
    await eventually(lambda: patch.call_count, lambda n: n == 1)

    # A successful toggle refreshes the table from the page's state
    emit_schedule_action(user, schedule, "toggle")
    await eventually(lambda: patch.call_count, lambda n: n == 2)
    assert schedule_row(user)["cron"] == "0 0 1 * *"
