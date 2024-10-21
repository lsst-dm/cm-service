"""FastAPI routers

Many of these routers are built using function templates defined in
lsst.cmservice.routers.wrappers

Most of these routers implement functions that manipulate individual
database tables.   Those routers will typically define a view variables
that specify which table is being manipulated, and then populate the
router using the wrapper template functions.


The exceptions to this pattern are:

index: top-level index
actions: specfic database actions
adders: adding things to the database (such as campaigns, steps or groups)
loaders: reading yaml files an loading objects into the database
queries: getting objects from the database
"""

from . import (
    actions,
    adders,
    campaigns,
    groups,
    index,
    jobs,
    loaders,
    pipetask_error_types,
    pipetask_errors,
    product_sets,
    productions,
    queries,
    queues,
    script_dependencies,
    script_errors,
    script_templates,
    scripts,
    spec_blocks,
    specifications,
    step_dependencies,
    steps,
    task_sets,
    wms_task_reports,
    wrappers,
)
