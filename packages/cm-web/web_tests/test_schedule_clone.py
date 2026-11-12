"""Tests for the page that clones a scheduled campaign, reached from the
schedule overview page.
"""

import pytest
from nicegui import ui
from nicegui.testing.user import User

from .conftest import FakeCMService


@pytest.mark.parametrize(
    "configuration",
    [
        {"auto_start": False, "expressions": {}, "name_format": "%Y%m%d_%s"},
        {"auto_start": False, "expressions": {}, "name_format": "%Y%m%d_%s", "cron": "30 6 * * *"},
    ],
    ids=["no configuration cron", "stale configuration cron"],
)
async def test_clone_uses_schedule_cron(user: User, cm_api: FakeCMService, configuration: dict) -> None:
    """Tests that a cloned schedule starts with its source schedule's cron,
    not a cron from the source's configuration or a default.
    """
    schedule = cm_api.add_schedule("monthly", cron="0 0 1 * *", configuration=configuration)
    await user.open(f"/schedules/{schedule['id']}")
    await user.should_see("Cron Expression", retries=30)
    (cron_input,) = user.find(kind=ui.input, content="Cron Expression").elements
    assert cron_input.value == "0 0 1 * *"
