"""Library module for supporting functions related to the schedules cli
command.
"""

from httpx2 import HTTPStatusError, Response
from rich.console import Console

from ..client import http_client
from ..models import TypedContext

console = Console()


def list_notification_labels(ctx: TypedContext) -> list:
    """List current notification labels."""
    r: Response | None = None
    with http_client(ctx) as client:
        try:
            r = client.get("/notifications/")
            r.raise_for_status()
        except HTTPStatusError as e:
            console.print(e.response.reason_phrase)
    if r is None:
        return []
    notifications = r.json()
    return notifications


def delete_notification_labels(ctx: TypedContext, label_name: str) -> None:
    """List current notification labels."""
    r: Response | None = None
    with http_client(ctx) as client:
        try:
            r = client.delete(f"/notifications/{label_name}")
            r.raise_for_status()
        except HTTPStatusError as e:
            console.print(e.response.reason_phrase)
