"""Module providing an httpx client for the cli application"""

from collections.abc import Generator
from contextlib import contextmanager
from uuid import uuid4

from httpx import Client, HTTPStatusError, HTTPTransport

from .logging import LOGGER
from .models import TypedContext

logger = LOGGER.bind(module=__name__)


@contextmanager
def http_client(ctx: TypedContext) -> Generator[Client]:
    """Generate a client session for cmclient API operations."""
    transport = HTTPTransport(
        verify=False,
        retries=3,
    )
    endpoint_url = ctx.obj.endpoint_url
    api_version = ctx.obj.api_version
    auth_token = ctx.obj.auth_token

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
            logger.error(e)
        except Exception as e:
            logger.error(e)
