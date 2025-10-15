"""Module providing an httpx client for the cli application"""

from collections.abc import Generator
from contextlib import contextmanager
from uuid import uuid4

import typer
from httpx import Client, HTTPStatusError, HTTPTransport

from .settings import settings


@contextmanager
def http_client(ctx: typer.Context) -> Generator[Client]:
    """Generate a client session for cmclient API operations."""
    transport = HTTPTransport(
        verify=False,
        retries=3,
    )
    endpoint_url = ctx.obj.get("endpoint_url", settings.endpoint)
    api_version = ctx.obj.get("api_version", settings.api_version)
    auth_token = ctx.obj.get("auth_token", settings.token)

    with Client(
        base_url=f"{endpoint_url}/{api_version}",
        follow_redirects=True,
        transport=transport,
        headers={
            "Authorization": f"Bearer {auth_token}",
            "X-Request-Id": f"{uuid4()}",
        },
    ) as session:
        try:
            yield session
        except HTTPStatusError as e:
            print(e)
        except Exception as e:
            print(e)
