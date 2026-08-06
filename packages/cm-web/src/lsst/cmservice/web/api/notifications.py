import json
from collections.abc import AsyncGenerator

from httpx import HTTPStatusError, codes
from nicegui import ui

from lsst.cmservice.models.api.notifications import NotificationLabelManifest

from ..lib.client_factory import CLIENT_FACTORY


async def get_notifications(label_name: str | None = None) -> AsyncGenerator[dict]:
    """Get a list of notification labels or a specific label."""
    url = "/notifications"
    if label_name is not None:
        url += f"/{label_name}"

    async with CLIENT_FACTORY.aclient() as client:
        try:
            r = await client.get(url)
            r.raise_for_status()
        except HTTPStatusError as e:
            detail = f"{e.response.status_code}: {e.response.reason_phrase}"
            ui.notify(detail)

    for label in r.json():
        yield label


async def new_notification_label(manifest: NotificationLabelManifest) -> None:
    """Create a new notification label with name and type."""
    url = "/notifications"

    async with CLIENT_FACTORY.aclient() as client:
        try:
            r = await client.post(url, json=manifest.model_dump())
            r.raise_for_status()
        except HTTPStatusError as e:
            match e.response.status_code:
                case codes.INTERNAL_SERVER_ERROR:
                    content = e.response.content.decode()
                    detail = json.loads(content).get("detail", "Internal Server Error")
                    ui.notify(detail, type="negative")


async def delete_notification_label(name: str) -> None:
    """Delete a new notification label with name and type."""
    url = f"/notifications/{name}"

    async with CLIENT_FACTORY.aclient() as client:
        try:
            r = await client.delete(url)
            r.raise_for_status()
        except HTTPStatusError as e:
            detail = f"{e.response.status_code}: {e.response.reason_phrase}"
            ui.notify(detail)
