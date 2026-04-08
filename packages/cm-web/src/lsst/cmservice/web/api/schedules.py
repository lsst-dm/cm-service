from collections.abc import AsyncGenerator

from httpx import AsyncClient


async def get_schedule_summary(client: AsyncClient) -> AsyncGenerator[dict]:
    """Gets a list of schedules known to the API."""
    r = await client.get("/schedules")
    r.raise_for_status()

    for schedule in r.json():
        yield schedule


async def toggle_schedule_state(client: AsyncClient) -> None:
    """PATCH a schedule to toggle its enabled status."""
    ...
