"""CLI commands

Many of these commands are built using function templates defined in
lsst.cmservice.cli.wrappers

Much of the CLI implements functions that manipulate individual
database tables.   Those functions will typically define a view variables
that specify which table is being manipulated, and then populate the
CLI using the wrapper template functions.


The exceptions to this pattern are:

action: specfic database actions
add: adding things to the database (such as campaigns, steps or groups)
load: reading yaml files an loading objects into the database
query: getting objects from the database
"""


from . import (
    action,
    add,
    campaign,
    commands,
    group,
    job,
    load,
    options,
    pipetask_error,
    pipetask_error_type,
    product_set,
    production,
    query,
    queue,
    script,
    script_dependency,
    script_error,
    script_template,
    spec_block,
    specificaiton,
    step,
    step_dependency,
    task_set,
    wms_task_report,
    wrappers,
)
