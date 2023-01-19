"""Tests for the cmservice.handlers.external module and routes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from cmservice.config import config


@pytest.mark.asyncio
async def test_get_index(client: AsyncClient) -> None:
    """Test ``GET /cm-service/``"""
    response = await client.get("/cm-service/")
    assert response.status_code == 200
    data = response.json()
    metadata = data["metadata"]
    assert metadata["name"] == config.name
    assert isinstance(metadata["version"], str)
    assert isinstance(metadata["description"], str)
    assert isinstance(metadata["repository_url"], str)
    assert isinstance(metadata["documentation_url"], str)
