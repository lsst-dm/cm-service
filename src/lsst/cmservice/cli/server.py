import click
import uvicorn
from safir.asyncio import run_with_asyncio

from .. import __version__


# build the server CLI
@click.group()
@click.version_option(version=__version__)
def server() -> None:
    """Administrative command-line interface for cm-service."""


@server.command(deprecated=True)
@click.option("--reset", is_flag=True, help="Delete all existing database data.")
@run_with_asyncio
async def init(*, reset: bool) -> None:  # pragma: no cover
    """Initialize the service database.

    .. deprecated:: v1.5.0
        The `init` command is deprecated in v0.2.0; it is replaced by alembic.
    """
    print("Use `alembic upgrade head` instead.")


@server.command()
@click.option("--port", default=8080, type=int, help="Port to run the application on.")
def run(port: int) -> None:  # pragma: no cover
    """Run the service application (for testing only)."""
    uvicorn.run("lsst.cmservice.main:app", host="0.0.0.0", port=port, reload=True, reload_dirs=["src"])


# Build the client CLI
@click.group(name="client")
@click.version_option(package_name="lsst-cm-service")
def client_top() -> None:
    """Administrative command-line interface client-side commands."""


if __name__ == "__main__":
    server()
