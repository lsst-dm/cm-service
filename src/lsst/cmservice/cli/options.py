from enum import Enum, auto
from functools import partial
from typing import Any, Callable, Type

import click
from click.decorators import FC

from ..client import CMClient

__all__ = [
    "cmclient",
    "output",
    "OutputEnum",
]


class EnumChoice(click.Choice):
    """A version of click.Choice specialized for enum types."""

    def __init__(self, enum: Type[Enum], case_sensitive: bool = True) -> None:
        self._enum = enum
        super().__init__(list(enum.__members__.keys()), case_sensitive=case_sensitive)

    def convert(self, value: Any, param: click.Parameter | None, ctx: click.Context | None) -> Enum:
        converted_str = super().convert(value, param, ctx)
        return self._enum.__members__[converted_str]


class PartialOption:
    """Wraps click.option decorator with partial arguments for convenient
    reuse."""

    def __init__(self, *param_decls: str, **attrs: Any) -> None:
        self._partial = partial(click.option, *param_decls, cls=partial(click.Option), **attrs)

    def __call__(self, *param_decls: str, **attrs: Any) -> Callable[[FC], FC]:
        return self._partial(*param_decls, **attrs)


class OutputEnum(Enum):
    yaml = auto()
    json = auto()


output = PartialOption(
    "--output",
    "-o",
    type=EnumChoice(OutputEnum),
    help="Output format.  Summary table if not specified.",
)


def make_client(ctx: click.Context, param: click.Parameter, value: Any) -> CMClient:
    return CMClient(value)


cmclient = PartialOption(
    "--server",
    "client",
    type=str,
    default="http://localhost:8080/cm-service/v1",
    envvar="CM_SERVICE",
    show_envvar=True,
    callback=make_client,
    help="URL of cm service.",
)
