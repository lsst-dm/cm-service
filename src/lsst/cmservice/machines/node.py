"""Module for state machine implementations related to Nodes.

Specific node machines are implemented in ``.nodes.*`` modules as imported for
export from this module.
"""

import inspect
import sys
from functools import cache

from ..common.enums import ManifestKind
from ..common.logging import LOGGER
from .nodes import TRANSITIONS as TRANSITIONS
from .nodes.meta import (
    EndMachine as EndMachine,
)
from .nodes.meta import (
    NodeMachine as NodeMachine,
)
from .nodes.meta import (
    StartMachine as StartMachine,
)
from .nodes.steps import (
    GroupMachine as GroupMachine,
)
from .nodes.steps import (
    StepCollectMachine as StepCollectMachine,
)
from .nodes.steps import (
    StepMachine as StepMachine,
)

logger = LOGGER.bind(module=__name__)


@cache
def node_machine_factory(kind: ManifestKind) -> type[NodeMachine]:
    """Returns the Stateful Model for a node based on its kind, by matching
    the ``__kind__`` attribute of available classes in this module.

    TODO: May "construct" new classes from multiple matches, but this is not
    yet necessary.
    """
    for _, o in inspect.getmembers(sys.modules[__name__], inspect.isclass):
        if issubclass(o, NodeMachine) and kind in o.__kind__:
            return o
    return NodeMachine
