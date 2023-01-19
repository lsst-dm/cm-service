import click
import structlog
import uvicorn
from safir.asyncio import run_with_asyncio
from safir.database import create_database_engine, initialize_database
from sqlalchemy.schema import CreateSchema

from ..config import config
from ..db import Base


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="lsst-cm-service")
def main() -> None:
    """Administrative command-line interface for cm-service."""


@main.command(name="help")
@click.argument("topic", default=None, required=False, nargs=1)
@click.pass_context
def help_command(ctx: click.Context, topic: str | None) -> None:
    """Show help for any command."""
    # The help command implementation is taken from
    # https://www.burgundywall.com/post/having-click-help-subcommand
    if topic:
        if topic in main.commands:
            click.echo(main.commands[topic].get_help(ctx))
        else:
            raise click.UsageError(f"Unknown help topic {topic}", ctx)
    else:
        assert ctx.parent
        click.echo(ctx.parent.get_help())


@main.command()
@click.option("--reset", is_flag=True, help="Delete all existing database data.")
@run_with_asyncio
async def init(reset: bool) -> None:  # pragma: no cover
    """Initialize the service database."""
    logger = structlog.get_logger(config.logger_name)
    engine = create_database_engine(config.database_url, config.database_password)
    # Remove this clause if Safir PR #140 is merged
    if Base.metadata.schema is not None:
        async with engine.begin() as conn:
            await conn.execute(CreateSchema(Base.metadata.schema, True))
    await initialize_database(engine, logger, schema=Base.metadata, reset=reset)
    await engine.dispose()


@main.command()
@click.option("--port", default=8080, type=int, help="Port to run the application on.")
def run(port: int) -> None:  # pragma: no cover
    """Run the service application (for testing only)."""
    uvicorn.run("lsst.cmservice.main:app", port=port, reload=True, reload_dirs=["src"])
