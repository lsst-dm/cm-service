import json
from dataclasses import dataclass
from typing import Generator, Iterable, TypeVar

import click
import structlog
import uvicorn
import yaml
from safir.asyncio import run_with_asyncio
from safir.database import create_database_engine, initialize_database
from tabulate import tabulate

from .. import models
from ..client import CMClient
from ..config import config
from ..db import Base
from . import options

T = TypeVar("T")


@click.group()
@click.version_option(package_name="lsst-cm-service")
def main() -> None:
    """Administrative command-line interface for cm-service."""


@main.group()
def get() -> None:
    """Display one or many resources."""


@get.command()
@options.cmclient()
@options.output()
def productions(client: CMClient, output: options.OutputEnum | None) -> None:
    """Display one or more productions."""
    productions = client.get_productions()
    match output:
        case options.OutputEnum.json:
            jtable = [p.dict() for p in productions]
            click.echo(json.dumps(jtable, indent=4))
        case options.OutputEnum.yaml:
            ytable = [p.dict() for p in productions]
            click.echo(yaml.dump(ytable))
        case _:
            ptable = [[p.name, p.id] for p in productions]
            click.echo(tabulate(ptable, headers=["NAME", "ID"], tablefmt="plain"))


@get.command()
@options.cmclient()
@options.output()
def campaigns(client: CMClient, output: options.OutputEnum | None) -> None:
    """Display one or more campaigns."""
    campaigns = client.get_campaigns()
    match output:
        case options.OutputEnum.json:
            jtable = [c.dict() for c in campaigns]
            click.echo(json.dumps(jtable, indent=4))
        case options.OutputEnum.yaml:
            ytable = [c.dict() for c in campaigns]
            click.echo(yaml.dump(ytable))
        case _:
            productions = client.get_productions()
            pbyid = {p.id: p.name for p in productions}
            ctable = [[c.name, pbyid.get(c.production, ""), c.id] for c in campaigns]
            click.echo(tabulate(ctable, headers=["NAME", "CAMPAIGN", "ID"], tablefmt="plain"))


@main.group()
def create() -> None:
    """Create a resource."""


@main.group()
def apply() -> None:
    """Apply configuration to a resource."""


@main.group()
def delete() -> None:
    """Delete a resource."""


def _lookahead(iterable: Iterable[T]) -> Generator[tuple[T, bool], None, None]:
    """A generator which returns all elements of the provided iteratable as
    tuples with an additional `bool`; the `bool` will be `True` on the last
    element and `False` otherwise."""
    it = iter(iterable)
    try:
        last = next(it)
    except StopIteration:
        return
    for val in it:
        yield last, False
        last = val
    yield last, True


@dataclass
class Root:
    name: str = "."


def _tree_prefix(last: list[bool]) -> str:
    prefix = ""
    for li, ll in _lookahead(last):
        match (ll, li):
            case (False, False):
                prefix += "│   "
            case (False, True):
                prefix += "    "
            case (True, False):
                prefix += "├── "
            case (True, True):  # pragma: no branch
                prefix += "└── "
    return prefix


def _tree_children(
    client: CMClient,
    node: Root | models.Production | models.Campaign | models.Step | models.Group,
) -> list:
    match node:
        case Root():
            return client.get_productions()
        case models.Production():
            return client.get_campaigns(node.id)
        case models.Campaign():
            return client.get_steps(node.id)
        case models.Step():
            return client.get_groups(node.id)
        case _:
            return []


def _tree1(
    client: CMClient,
    node: Root | models.Production | models.Campaign | models.Step | models.Group,
    last: list[bool],
) -> None:
    click.echo(_tree_prefix(last) + node.name)
    last.append(True)
    for child, last[-1] in _lookahead(_tree_children(client, node)):
        _tree1(client, child, last)
    last.pop()


@main.command()
@options.cmclient()
@click.argument("path", required=False)
def tree(client: CMClient, path: str | None) -> None:
    """List resources recursively beneath PATH."""
    _tree1(client, Root(), [])


@main.command()
@click.option("--reset", is_flag=True, help="Delete all existing database data.")
@run_with_asyncio
async def init(reset: bool) -> None:  # pragma: no cover
    """Initialize the service database."""
    logger = structlog.get_logger(config.logger_name)
    engine = create_database_engine(config.database_url, config.database_password)
    await initialize_database(engine, logger, schema=Base.metadata, reset=reset)
    await engine.dispose()


@main.command()
@click.option("--port", default=8080, type=int, help="Port to run the application on.")
def run(port: int) -> None:  # pragma: no cover
    """Run the service application (for testing only)."""
    uvicorn.run("lsst.cmservice.main:app", host="0.0.0.0", port=port, reload=True, reload_dirs=["src"])
