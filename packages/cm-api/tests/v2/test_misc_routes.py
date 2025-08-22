"""Tests for miscellaneous routes."""

from uuid import uuid4

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


async def test_activity_log_routes(
    aclient: AsyncClient, caplog: pytest.LogCaptureFixture, test_campaign: str
) -> None:
    """Tests the activity log multipurpose collection route, ensuring that
    query parameters behave as expected to generate executable SQL to satisfy
    the request.
    """
    # Test multiple query parameters at once
    y = await aclient.get(
        f"/cm-service/v2/logs?pilot=bobloblaw&campaign={uuid4()}&node={uuid4()}&since=1989-06-03T12:34:56Z"
    )
    assert y.is_success

    # Test a different datetime format
    y = await aclient.get("/cm-service/v2/logs?pilot=bobloblaw&since=946684800")
    assert y.is_success
