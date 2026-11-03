"""Tests that each cm-web page renders against the fake API."""

import pytest
from nicegui.testing.user import User

from .conftest import FakeCMService


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/", "nostromo"),
        ("/campaign/{campaign_id}", "ripley"),
        ("/node/{node_id}", "ripley"),
        ("/clone/{campaign_id}", "Cloned Campaign"),
        ("/new_campaign", "New Campaign"),
        ("/notifications", "Notifications Overview"),
        ("/schedules", "Schedule Overview"),
        ("/canvas", "Canvas Scratch Pad"),
        ("/help", "CM Service Help"),
    ],
)
async def test_page_renders(user: User, cm_api: FakeCMService, path: str, expected: str) -> None:
    campaign = cm_api.add_campaign("nostromo", nodes=["ripley", "dallas"])
    node = cm_api.add_node(campaign["id"], "ripley")
    await user.open(path.format(campaign_id=campaign["id"], node_id=node["id"]))
    await user.should_see(expected)
