from collections.abc import Callable
from enum import Enum, auto
from functools import partial
from typing import Any

import click
from click.decorators import FC

from ..client.client import CMClient
from ..common.enums import ErrorActionEnum, ErrorFlavorEnum, ErrorSourceEnum, NodeTypeEnum, StatusEnum

__all__ = [
    "cmclient",
    "output",
    "OutputEnum",
    "alias",
    "allow_update",
    "collections",
    "campaign_yaml",
    "child_config",
    "child_configs",
    "data",
    "data_id",
    "depend_id",
    "diagnostic_message",
    "error_action",
    "error_flavor",
    "error_source",
    "error_type_id",
    "fake_status",
    "fullname",
    "interval",
    "job_id",
    "handler",
    "n_expected",
    "name",
    "node_type",
    "parent_name",
    "parent_id",
    "prereq_id",
    "quanta",
    "rematch",
    "row_id",
    "script_template_name",
    "script_name",
    "scripts",
    "spec_aliases",
    "spec_block_name",
    "spec_block_assoc_name",
    "spec_name",
    "status",
    "superseded",
    "task_id",
    "task_name",
    "update_dict",
    "wms_job_id",
    "yaml_file",
]


class DictParamType(click.ParamType):
    """Represents the dictionary type of a CLI parameter.

    Validates and converts values from the command line string or Python into
    a Python dict.
        - All key-value pairs must be separated by one semicolon.
        - Key and value must be separated by one colon
        - Converts sequences separeted by dots into a list: list value items
              must be separated by commas.
        - Converts numbers to int.

    Usage
        >>> @click.option("--param", default=None, type=DictParamType())
        ... def command(param):
        ...     ...

        CLI: command --param='page:1; name=Items; rules=1, 2, three; extra=A,;'

    Example
    -------
        >>> param_value = 'page=1; name=Items; rules:1, 2, three; extra=A,;'
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

        Parameters
        ----------
        value: Any
            The value to convert.
        param: (click.Parameter | None)
            The parameter that is using this type to convert its value.
        ctx:  (click.Context | None)
            The current context that arrived at this value.

        Returns
        -------
            dict: The validated and converted dictionary.

        Raises
        ------
            click.BadParameter: If the validation is failed.
        """
        if isinstance(value, dict):
            return value
        try:
            keyvalue_pairs = value.rstrip(";").split(";")
            result_dict = {}
            for pair in keyvalue_pairs:
                key, value = (item.strip() for item in pair.split(":"))
                result_dict[key] = value
            return result_dict
        except ValueError:
            self.fail(
                "All key-value pairs must be separated by one semicolon. "
                "Key and value must be separated by one colon. "
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
        self._partial = partial(click.option, *param_decls, cls=click.Option, **attrs)

    def __call__(self: "PartialOption", *param_decls: str, **attrs: Any) -> Callable[[FC], FC]:
        return self._partial(*param_decls, **attrs)


class OutputEnum(Enum):
    """Options for output format"""

    yaml = auto()  # pylint: disable=invalid-name
    json = auto()  # pylint: disable=invalid-name


output = PartialOption(
    "--output",
    "-o",
    type=EnumChoice(OutputEnum),
    help="Output format.  Summary table if not specified.",
)


alias = PartialOption(
    "--alias",
    type=str,
    default=None,
    help="Alias for a ScriptTemplate or SpecBlock association",
)


campaign_yaml = PartialOption(
    "--campaign_yaml",
    type=str,
    help="Path to campaign yaml file",
)


allow_update = PartialOption(
    "--allow_update",
    is_flag=True,
    default=False,
    help="Allow updates when loading yaml files",
)


collections = PartialOption(
    "--collections",
    type=DictParamType(),
    help="collections values to update",
)

child_config = PartialOption(
    "--child_config",
    type=DictParamType(),
    help="child_config values to update",
)

child_configs = PartialOption(
    "--child_configs",
    type=DictParamType(),
    help="child_configurations",
)


data = PartialOption(
    "--data",
    type=DictParamType(),
    help="data values to update",
)


data_id = PartialOption(
    "--data_id",
    type=DictParamType(),
    help="Butler Data ID associated to the errror",
)


depend_id = PartialOption(
    "--depend_id",
    type=int,
    help="ID of dependent Node",
)


diagnostic_message = PartialOption(
    "--diagnostic_message",
    type=str,
    help="Diagnostic message associated to the error",
)


fake_status = PartialOption(
    "--fake_status",
    type=EnumChoice(StatusEnum),
    default=None,
    help="Status to set for Element",
)


error_action = PartialOption(
    "--error_action",
    type=EnumChoice(ErrorActionEnum),
    default=ErrorActionEnum.review,
    help="Action to take for this error",
)


error_flavor = PartialOption(
    "--error_flavor",
    type=EnumChoice(ErrorFlavorEnum),
    default=ErrorFlavorEnum.pipelines,
    help="Flavor of this error",
)

error_source = PartialOption(
    "--error_source",
    type=EnumChoice(ErrorSourceEnum),
    default=ErrorSourceEnum.manifest,
    help="Source of this error",
)


error_type_id = PartialOption(
    "--error_type_id",
    type=int,
    default=None,
    help="Error type",
)


fake_status = PartialOption(
    "--fake_status",
    type=EnumChoice(StatusEnum),
    default=None,
    help="Status to set for Element",
)


fullname = PartialOption(
    "--fullname",
    type=str,
    help="Full name of object in DB.",
)


interval = PartialOption(
    "--interval",
    type=int,
    help="Interval between process calls (s)",
    default=300,
)


job_id = PartialOption(
    "--job_id",
    type=int,
    help="ID of associated job",
)


handler = PartialOption("--handler", type=str, help="Name of object")


n_expected = PartialOption(
    "--n_expected",
    type=int,
    help="Number of expected outputs",
)


name = PartialOption("--name", type=str, help="Name of object")


node_type = PartialOption(
    "--node_type",
    type=EnumChoice(NodeTypeEnum),
    default=NodeTypeEnum.element.name,
    help="What type of table, used to select scripts and jobs",
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


prereq_id = PartialOption(
    "--prereq_id",
    type=int,
    help="ID of prerequisite node",
)


quanta = PartialOption(
    "--quanta",
    type=str,
    help="QG quanta ID",
)


rematch = PartialOption(
    "--rematch",
    is_flag=True,
    help="Rematch Errors",
)


row_id = PartialOption(
    "--row_id",
    type=int,
    help="ID of object.",
)


script_template_name = PartialOption(
    "--script_template_name",
    type=str,
    help="Name of a ScriptTemplate",
)


scripts = PartialOption(
    "--scripts",
    type=DictParamType(),
    help="Description of scripts associated to a Node",
)


script_name = PartialOption(
    "--script_name",
    type=str,
    help="Used to distinguish scripts within an Element",
)


spec_block_assoc_name = PartialOption(
    "--spec_block_assoc_name",
    type=str,
    help="Combined name of Specification and SpecBlock",
)


spec_block_name = PartialOption(
    "--spec_block_name",
    type=str,
    help="Name of the SpecBlock",
)


spec_name = PartialOption(
    "--spec_name",
    type=str,
    help="Name of the specification",
)


spec_aliases = PartialOption(
    "--spec_aliases",
    type=DictParamType(),
    help="Spec aliases to update",
)


status = PartialOption(
    "--status",
    type=EnumChoice(StatusEnum),
    help="Status to set for Element",
)


superseded = PartialOption(
    "--superseded",
    is_flag=True,
    help="Mark element as superseded",
)


task_id = PartialOption(
    "--task_id",
    type=int,
    help="ID of the associated task",
)


task_name = PartialOption(
    "--task_name",
    type=str,
    help="Name of pipetask with error",
)


update_dict = PartialOption(
    "--update_dict",
    type=DictParamType(),
    help="Values to update",
)

wms_job_id = PartialOption(
    "--wms_job_id",
    type=str,
    help="ID for job in Workflow management system",
)


yaml_file = PartialOption(
    "--yaml_file",
    type=str,
    help="Path to yaml file",
)


def make_client(_ctx: click.Context, _param: click.Parameter, value: Any) -> CMClient:
    """Build and return a CMCLient object"""
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
