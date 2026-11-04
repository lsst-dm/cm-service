"""Module providing an httpx2 client for the cli application"""

from collections.abc import Generator
from contextlib import contextmanager
from uuid import uuid4

import typer
from httpx2 import Client, HTTPTransport
from typer.exceptions import TyperException

from .logging import LOGGER
from .models import TypedContext

logger = LOGGER.bind(module=__name__)


@contextmanager
def http_client(ctx: TypedContext) -> Generator[Client]:
    """Generate a client session for cmclient API operations.

    Any error raised in the client context, other than a command's own exit,
    abort, or usage error, is logged and ends the command with exit code 1.
    """
    transport = HTTPTransport(
        verify=False,
        retries=3,
    )
    endpoint_url = ctx.obj.endpoint_url
    api_version = ctx.obj.api_version
    auth_token = ctx.obj.auth_token
    user = ctx.obj.user

    headers = {"X-Request-Id": f"{uuid4()}"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    if user:
        headers["X-Auth-Request-User"] = user

    with Client(
        base_url=f"{endpoint_url}/{api_version}",
        follow_redirects=True,
        transport=transport,
        headers=headers,
    ) as client:
        try:
            yield client
        except typer.Exit, typer.Abort, TyperException:
            # A command's own exit, abort, or usage error passes through as is
            raise
        except Exception as e:
            # Any other error ends the command with a failure exit code instead
            # of letting the command continue after the client context
            logger.error(e)
            raise typer.Exit(1) from e
