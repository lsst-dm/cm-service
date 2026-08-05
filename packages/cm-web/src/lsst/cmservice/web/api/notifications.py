from collections.abc import AsyncGenerator

from lsst.cmservice.models.api.notifications import NotificationLabelManifest

from ..lib.client_factory import CLIENT_FACTORY


async def get_notifications(label_name: str | None = None) -> AsyncGenerator[dict]:
    """Get a list of notification labels or a specific label."""
    url = "/notifications"
    if label_name is not None:
        url += f"/{label_name}"

    async with CLIENT_FACTORY.aclient() as client:
        r = await client.get(url)
        r.raise_for_status()

    for label in r.json():
        yield label


async def new_notification_label(manifest: NotificationLabelManifest) -> None:
    """Create a new notification label with name and type."""
    url = "/notifications"

    async with CLIENT_FACTORY.aclient() as client:
        r = await client.post(url, json=manifest.model_dump())
        r.raise_for_status()


async def delete_notification_label(name: str) -> None:
    """Delete a new notification label with name and type."""
    url = f"/notifications/{name}"

    async with CLIENT_FACTORY.aclient() as client:
        r = await client.delete(url)
        r.raise_for_status()
