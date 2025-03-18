import click

from .. import __version__
from .action import action_group
from .campaign import campaign_group
from .group import group_group
from .job import job_group
from .load import load_group
from .pipetask_error import pipetask_error_group
from .pipetask_error_type import pipetask_error_type_group
from .product_set import product_set_group
from .queue import queue_group
from .script import script_group
from .script_dependency import script_dependency_group
from .script_error import script_error_group
from .spec_block import spec_block_group
from .specification import specification_group
from .step import step_group
from .step_dependency import step_dependency_group
from .task_set import task_set_group
from .wms_task_report import wms_task_report_group


# Build the client CLI
@click.group(
    name="client",
    commands=[
        action_group,
        campaign_group,
        group_group,
        job_group,
        load_group,
        pipetask_error_group,
        pipetask_error_type_group,
        product_set_group,
        queue_group,
        script_group,
        script_dependency_group,
        script_error_group,
        spec_block_group,
        specification_group,
        step_dependency_group,
        step_group,
        task_set_group,
        wms_task_report_group,
    ],
)
@click.version_option(version=__version__)
def client_top() -> None:
    """Administrative command-line interface client-side commands."""


if __name__ == "__main__":
    client_top()
