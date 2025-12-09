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
    actions as actions,
)
from . import (
    campaigns as campaigns,
)
from . import (
    groups as groups,
)
from . import (
    index as index,
)
from . import (
    jobs as jobs,
)
from . import (
    loaders as loaders,
)
from . import (
    pipetask_error_types as pipetask_error_types,
)
from . import (
    pipetask_errors as pipetask_errors,
)
from . import (
    product_sets as product_sets,
)
from . import (
    queues as queues,
)
from . import (
    script_dependencies as script_dependencies,
)
from . import (
    script_errors as script_errors,
)
from . import (
    scripts as scripts,
)
from . import (
    spec_blocks as spec_blocks,
)
from . import (
    specifications as specifications,
)
from . import (
    step_dependencies as step_dependencies,
)
from . import (
    steps as steps,
)
from . import (
    task_sets as task_sets,
)
from . import (
    wms_task_reports as wms_task_reports,
)
from . import (
    wrappers as wrappers,
)

tags_metadata = [
    {
        "name": "actions",
        "description": "Operations perform actions on existing Objects in to the DB."
        "In many cases this will result in the creating of new objects in the DB.",
    },
    {
        "name": "campaigns",
        "description": "Operations with `campaign`s. A `campaign` consists of several processing `step`s "
        "which are run sequentially. A `campaign` also holds configuration such as a URL for a butler repo "
        "and a production area. `campaign`s must be uniquely named withing a given `production`.",
    },
    {
        "name": "edges",
        "description": "Operations with `edge`s within a `campaign` graph.",
    },
    {
        "name": "groups",
        "description": "Operations with `groups`. A `group` can be processed in a single `workflow`, "
        "but we also need to account for possible failures. `group`s must be uniquely named within a "
        "given `step`.",
    },
    {
        "name": "health",
        "description": "Operations that check or report on the health of the application",
    },
    {
        "name": "internal",
        "description": "Operations that are used by processes that are internal to the application",
    },
    {
        "name": "jobs",
        "description": "Operations with `jobs`. A `job` runs a single `workflow`: keeps a count"
        "of the results data products and keeps track of associated errors.",
    },
    {
        "name": "loaders",
        "description": "Operations that load Objects in to the DB.",
    },
    {
        "name": "manifests",
        "description": "Operations on manifests.",
    },
    {
        "name": "pipetask error types",
        "description": "Operations with `pipetask_error_type` table.",
    },
    {
        "name": "pipetask errors",
        "description": "Operations with `pipetask_error` table.",
    },
    {
        "name": "product sets",
        "description": "Operations with `product_set` table.",
    },
    {
        "name": "scripts",
        "description": "Operations with `scripts`. A `script` does a single operation, either something"
        "that is done asynchronously, such as making new collections in the Butler, or creating"
        "new objects in the DB, such as new `steps` and `groups`.",
    },
    {
        "name": "script dependencies",
        "description": "Operations with `script_dependency` table.",
    },
    {
        "name": "script errors",
        "description": "Operations with `script_errors` table.",
    },
    {"name": "spec blocks", "description": "Operations with `spec_block` table."},
    {"name": "specifications", "description": "Operations with `specification` table."},
    {
        "name": "steps",
        "description": "Operations with `step`s. A `step` consists of several processing `group`s which "
        "may be run in parallel. `step`s must be uniquely named within a give `campaign`.",
    },
    {
        "name": "step dependencies",
        "description": "Operations with `step_dependency` table.",
    },
    {
        "name": "task sets",
        "description": "Operations with `task_set` table.",
    },
    {
        "name": "v1",
        "description": "Operations associated with the v1 legacy application",
    },
    {
        "name": "v2",
        "description": "Operations associated with the v2 application",
    },
    {
        "name": "wms task reports",
        "description": "Operations with `wms_task_report` table.",
    },
]
