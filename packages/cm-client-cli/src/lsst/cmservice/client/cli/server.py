import warnings

import click
from safir.asyncio import run_with_asyncio

from .. import __version__


# build the server CLI
@click.group()
@click.version_option(version=__version__)
def server() -> None:
    """Administrative command-line interface for cm-service.

    .. deprecated:: v0.2.0
        The `server` command is deprecated in v0.2.0
    """


@server.command(deprecated=True)
@click.option("--reset", is_flag=True, help="Delete all existing database data.")
@run_with_asyncio
async def init(*, reset: bool) -> None:  # pragma: no cover
    """Initialize the service database.

    .. deprecated:: v0.2.0
        The `init` command is deprecated in v0.2.0; it is replaced by alembic.
    """
    warnings.warn("Use `alembic upgrade head` instead.", DeprecationWarning)


@server.command()
@click.option("--port", default=8080, type=int, help="Port to run the application on.")
def run(port: int) -> None:  # pragma: no cover
    """Run the service application (for testing only).

    .. deprecated:: v0.2.0
        The `run` command is deprecated in v0.2.0. Launch the server with a
        module entrypoint instead.
    """
    warnings.warn("Use `python3 -m lsst.cmservice.main` instead.", DeprecationWarning)


# Build the client CLI
@click.group(name="client")
@click.version_option(package_name="lsst-cm-service")
def client_top() -> None:
    """Administrative command-line interface client-side commands."""


if __name__ == "__main__":
    server()
