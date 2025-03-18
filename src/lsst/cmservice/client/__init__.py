"""python client API

Much of this API is built using function templates defined in
lsst.cmservice.client.wrappers and is implemeted as many sub-clients.

Most of these sub-clients implement functions that manipulate individual
database tables.   Those will typically define a few variables
that specify which table is being manipulated, and then populate the
sub-client class using the wrapper template functions.

The exceptions to this pattern are:

index: top-level index
actions: specfic database actions
adders: adding things to the database (such as campaigns, steps or groups)
loaders: reading yaml files an loading objects into the database
queries: getting objects from the database
"""


from .actions import CMActionClient
from .campaigns import CMCampaignClient
from .client import CMClient
from .groups import CMGroupClient
from .jobs import CMJobClient
from .loaders import CMLoadClient
from .pipetask_error_types import CMPipetaskErrorTypeClient
from .pipetask_errors import CMPipetaskErrorClient
from .product_sets import CMProductSetClient
from .productions import CMProductionClient
from .queues import CMQueueClient
from .script_dependencies import CMScriptDependencyClient
from .script_errors import CMScriptErrorClient
from .scripts import CMScriptClient
from .spec_blocks import CMSpecBlockClient
from .specifications import CMSpecificationClient
from .step_dependencies import CMStepDependencyClient
from .steps import CMStepClient
from .task_sets import CMTaskSetClient
from .wms_task_reports import CMWmsTaskReportClient

__all__ = [
    "CMActionClient",
    "CMCampaignClient",
    "CMClient",
    "CMGroupClient",
    "CMJobClient",
    "CMLoadClient",
    "CMPipetaskErrorTypeClient",
    "CMPipetaskErrorClient",
    "CMProductSetClient",
    "CMProductionClient",
    "CMQueueClient",
    "CMScriptDependencyClient",
    "CMScriptErrorClient",
    "CMScriptClient",
    "CMSpecBlockClient",
    "CMSpecificationClient",
    "CMStepDependencyClient",
    "CMStepClient",
    "CMTaskSetClient",
    "CMWmsTaskReportClient",
]
