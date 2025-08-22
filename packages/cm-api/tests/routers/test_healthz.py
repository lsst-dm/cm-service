import pytest
from httpx import AsyncClient


@pytest.mark.asyncio()
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
async def test_get_healthz(client: AsyncClient) -> None:
    """Test ``GET /healthz``."""
    response = await client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["name"], str)
    assert isinstance(data["version"], str)
