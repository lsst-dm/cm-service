from collections.abc import AsyncGenerator

from httpx import AsyncClient

from lsst.cmservice.models.db.schedules import ManifestTemplateBase

from ..lib.client_factory import CLIENT_FACTORY


async def get_schedule_summary(client: AsyncClient) -> AsyncGenerator[dict]:
    """Gets a list of schedules known to the API."""
    r = await client.get("/schedules")
    r.raise_for_status()

    for schedule in r.json():
        yield schedule


async def toggle_schedule_state(schedule_id: str) -> None:
    """PATCH a schedule to toggle its enabled status."""
    ...


async def get_schedule_templates(schedule_id: str) -> AsyncGenerator[ManifestTemplateBase]:
    async with CLIENT_FACTORY.aclient() as client:
        r = await client.get(f"/schedules/{schedule_id}/templates")
        r.raise_for_status()

        for template in r.json():
            yield ManifestTemplateBase(**template)
