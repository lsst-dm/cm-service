from collections.abc import Callable
from enum import Enum, auto
from functools import partial
from typing import Any

import click
from click.decorators import FC

from ..client.client import CMClient
from ..common.enums import NodeTypeEnum, StatusEnum

__all__ = [
    "cmclient",
    "output",
    "OutputEnum",
    "collections",
    "child_config",
    "child_configs",
    "data",
    "fake_status",
    "fullname",
    "interval",
    "handler",
    "name",
    "node_type",
    "parent_name",
    "parent_id",
    "rematch",
    "row_id",
    "script_name",
    "spec_name",
    "spec_block_name",
    "spec_aliases",
    "status",
    "update_dict",
    "yaml_file",
]


class DictParamType(click.ParamType):
    """Represents the dictionary type of a CLI parameter.

    Validates and converts values from the command line string or Python into
    a Python dict.
        - All key-value pairs must be separated by one semicolon.
        - Key and value must be separated by one equal sign.
        - Converts sequences separeted by dots into a list: list value items
              must be separated by commas.
        - Converts numbers to int.

    Usage:
        >>> @click.option("--param", default=None, type=DictParamType())
        ... def command(param):
        ...     ...

        CLI: command --param='page=1; name=Items; rules=1, 2, three; extra=A,;'

    Example:

        >>> param_value = 'page=1; name=Items; rules=1, 2, three; extra=A,;'
        >>> DictParamType().convert(param_value, None, None)
        {'page': 1, 'name': 'Items', 'rules': [1, 2, 'three'], 'extra': ['A']}`

    """

    name = "dictionary"

    def convert(  # pylint:  disable=inconsistent-return-statements
        self,
        value: Any,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> dict:
        """Converts CLI value to the dictionary structure.

        Args:
            value (Any): The value to convert.
            param (click.Parameter | None): The parameter that is using this
                type to convert its value.
            ctx (click.Context | None): The current context that arrived
                at this value.

        Returns:
            dict: The validated and converted dictionary.

        Raises:
            click.BadParameter: If the validation is failed.
        """
        if isinstance(value, dict):
            return value
        try:
            keyvalue_pairs = value.rstrip(";").split(";")
            result_dict = {}
            for pair in keyvalue_pairs:
                key, values = (item.strip() for item in pair.split("="))
                converted_values = []
                for value_ in values.split(","):
                    value_ = value_.strip()
                    if value_.isdigit():
                        value_ = int(value_)
                    converted_values.append(value_)

                if len(converted_values) == 1:
                    result_dict[key] = converted_values[0]
                elif len(converted_values) > 1 and converted_values[-1] == "":
                    result_dict[key] = converted_values[:-1]
                else:
                    result_dict[key] = converted_values
            return result_dict
        except ValueError:
            self.fail(
                "All key-value pairs must be separated by one semicolon. "
                "Key and value must be separated by one equal sign. "
                "List value items must be separated by one comma. "
                f"Key-value: {pair}.",
                param,
                ctx,
            )


class EnumChoice(click.Choice):
    """A version of click.Choice specialized for enum types."""

    def __init__(self: "EnumChoice", enum: type[Enum], *, case_sensitive: bool = True) -> None:
        self._enum = enum
        super().__init__(list(enum.__members__.keys()), case_sensitive=case_sensitive)

    def convert(
        self: "EnumChoice",
        value: Any,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> Enum:
        converted_str = super().convert(value, param, ctx)
        return self._enum.__members__[converted_str]


class PartialOption:
    """Wrap partially specified click.option decorator for convenient reuse."""

    def __init__(self: "PartialOption", *param_decls: str, **attrs: Any) -> None:
        self._partial = partial(click.option, *param_decls, cls=partial(click.Option), **attrs)

    def __call__(self: "PartialOption", *param_decls: str, **attrs: Any) -> Callable[[FC], FC]:
        return self._partial(*param_decls, **attrs)


class OutputEnum(Enum):
    yaml = auto()
    json = auto()


collections = PartialOption(
    "--collections",
    type=DictParamType(),
    help="collections values to update",
)

child_configs = PartialOption(
    "--child_configs",
    type=dict,
    help="child_configurations",
)


child_config = PartialOption(
    "--child_config",
    type=DictParamType(),
    help="child_config values to update",
)


data = PartialOption(
    "--data",
    type=DictParamType(),
    help="data values to update",
)


fake_status = PartialOption(
    "--fake_status",
    type=EnumChoice(StatusEnum),
    default=None,
    help="Status to set for Element",
)


output = PartialOption(
    "--output",
    "-o",
    type=EnumChoice(OutputEnum),
    help="Output format.  Summary table if not specified.",
)


fullname = PartialOption(
    "--fullname",
    type=str,
    help="Full name of object in DB.",
)

parent_name = PartialOption(
    "--parent_name",
    type=str,
    default=None,
    help="Full name of parent object in DB.",
)

parent_id = PartialOption(
    "--parent_id",
    type=int,
    default=None,
    help="ID of parent object in DB.",
)

handler = PartialOption("--handler", type=str, help="Name of object")


row_id = PartialOption(
    "--row_id",
    type=int,
    help="ID of object.",
)

interval = PartialOption(
    "--interval",
    type=int,
    help="Interval between process calls (s)",
    default=300,
)

name = PartialOption("--name", type=str, help="Name of object")

node_type = PartialOption(
    "--node_type",
    type=EnumChoice(NodeTypeEnum),
    default=NodeTypeEnum.element.name,
    help="What type of table, used to select scripts and jobs",
)

rematch = PartialOption(
    "--rematch",
    is_flag=True,
    help="Rematch Errors",
)

status = PartialOption(
    "--status",
    type=EnumChoice(StatusEnum),
    help="Status to set for Element",
)

script_name = PartialOption(
    "--script_name",
    type=str,
    help="Used to distinguish scripts within an Element",
)

spec_name = PartialOption(
    "--spec_name",
    type=str,
    help="Name of the specification",
)


spec_block_name = PartialOption(
    "--spec_block_name",
    type=str,
    help="Name of the SpecBlock",
)


spec_aliases = PartialOption(
    "--spec_aliases",
    type=DictParamType(),
    help="Spec aliases to update",
)


update_dict = PartialOption(
    "--update_dict",
    type=DictParamType(),
    help="Values to update",
)

yaml_file = PartialOption(
    "--yaml_file",
    type=str,
    help="Path to yaml file",
)


def make_client(_ctx: click.Context, _param: click.Parameter, value: Any) -> CMClient:
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
