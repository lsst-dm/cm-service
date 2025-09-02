"""CLI commands

Many of these commands are built using function templates defined in
lsst.cmservice.cli.wrappers

Much of the CLI implements functions that manipulate individual
database tables.   Those functions will typically define a view variables
that specify which table is being manipulated, and then populate the
CLI using the wrapper template functions.


The exceptions to this pattern are:

action: specfic database actions
load: reading yaml files an loading objects into the database
query: getting objects from the database
"""

from ..common.logging import LOGGER as LOGGER
