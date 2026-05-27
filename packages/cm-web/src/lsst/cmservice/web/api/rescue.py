r"""

Rescue GROUP operation is a chain of api calls to

1. PAUSE campaign for updates

2. mark a failed GROUP or RESCUE "accepted"

3. create a new RESCUE node in the campaign.

    - RESCUE == GROUP or previous RESCUE with config change (bps option)
    - extra-qgraph-options: --skip-existing-in ...

4. ADD NEW GROUP to graph after RESCUED NODE

The collection list for "skip-existing-in" is the comma-separated list of any
preceeding groups in the rescue chain:

STEP -> GROUP -> RESCUE -> [RESCUE ->] COLLECT
        ^^^^^    ^^^^^^     ^^^^^^
        \________skips in
         \______________\___skips in

Notes
-----
- The configuration for a group is the completely baked configuration chain, so
  additional manifest lookups should not be necessary.
- The "trailing" run collection should therefore be part of the configuration
  of the GROUP or RESCUE being rescued.
- In case of a RESCUE chain, the bps option just keeps getting longer, with the
  latest run collection appended to the list of collections.

Double Check
------------
- [ ] The API allows creation of new GROUP nodes.
- [ ] Should the action be performed on a FAILED group, with marking acceptance
      part of the workflow, or only available on ACCEPTED groups, irrespective
      of how they got that way?
"""

import re
from types import SimpleNamespace
from typing import cast

from httpx import HTTPStatusError
from nicegui.events import ValueChangeEventArguments

from lsst.cmservice.models.db.campaigns import Node

from ..lib.models import STEP_MANIFEST_TEMPLATE
from .campaigns import toggle_campaign_state
from .manifests import put_manifest_list
from .nodes import get_one_node, insert_or_append_node, retry_restart_node


async def rescue_group(n0: str) -> str:
    """Performs a rescue workflow for a failed group.

    This workflow uses prescribed API operation primitives from other workflows
    so does not access an HTTP client through dependency injection or factory
    functions; client management is handled within the other primitives.

    Returns
    -------
    str
        The string UUID of the new rescue group
    """
    try:
        # Since we have only the group ID, fetch the entire Group object from
        # the API and extract its parent campaign.
        if (r := await get_one_node(id=n0, namespace=None)) is not None:
            node = Node.model_validate_json(r.content)
            # Pause the campaign
            campaign_id: str = str(node.namespace)
        else:
            raise RuntimeError("Could not obtain node and/or campaign information for group")
        e = cast(ValueChangeEventArguments, SimpleNamespace(value=False))
        await toggle_campaign_state(e, {"id": campaign_id})

    except (RuntimeError, HTTPStatusError) as e:
        raise RuntimeError("Could not retrieve target Node") from e

    # Identify the trailing collections with the partial work
    group_output = node.configuration["butler"]["collections"].pop("group_output")
    group_run = node.configuration["butler"]["collections"].pop("run")

    # for the bps option, we locate the `extra_qgraph_options` param
    extra_qgraph_options: list[str] = node.configuration.get("bps", {}).get("extra_qgraph_options", [])

    # Locate any existing `skip-existing-in` option in the param list
    option_stem = "--skip-existing-in"
    pattern = re.compile(rf"^{option_stem}\s+(?P<collections>\S+)$")
    found_option = False

    for i, opt in enumerate(extra_qgraph_options):
        m = pattern.match(opt)
        if m:
            # Update the existing option
            skipped_collections: list[str] = m.group("collections").split(",")
            skipped_collections.append(group_run)
            extra_qgraph_options[i] = f"{option_stem} {','.join(skipped_collections)}"
            found_option = True

    if not found_option:
        # Add a new option
        extra_qgraph_options.append(f"{option_stem} {group_run}")

    # Update the Node configuration to reflect a Rescue operation
    rescue_count: int = node.metadata_.get("rescues", 0) + 1
    rescue_name = f"{node.name}_rescue_{rescue_count}"

    # Apply the updated bps options in the new rescue group
    node.configuration["bps"]["extra_qgraph_options"] = extra_qgraph_options

    collections: dict = node.configuration["butler"].pop("collections", {})
    # change butler.collections.group_output to `*/rescue_NNN`
    collections["group_output"] = f"{group_output}/rescue_{rescue_count:03d}"
    # change butler.collections.run to `*/rescue_NNN_version_Y`
    collections["run"] = f"{group_run}/rescue_{rescue_count:03d}"
    node.configuration["butler"]["collections"] = collections

    # NOTE unlike group nodes created during step preparation, the ID generated
    # for this rescue group will be performed by the API like other nodes.
    rescue_manifest = STEP_MANIFEST_TEMPLATE | {
        "spec": node.configuration,
        "metadata": {
            "name": rescue_name,
            "namespace": campaign_id,
            "kind": "group",
            "version": 0,
            "rescues": rescue_count,
        },
    }

    # put the rescue group into the campaign
    try:
        if await put_manifest_list([rescue_manifest]):
            # fetch the new rescue group
            if (r := await get_one_node(id=rescue_name, namespace=campaign_id)) is None:
                raise RuntimeError("Failed to fetch new rescue group node")
            rescue: dict = r.json()
        else:
            raise RuntimeError("Failed to create new rescue group node")

        # put the rescue group into the graph (insert)
        await insert_or_append_node(n0=n0, n1=rescue["id"], namespace=campaign_id, operation="insert")

        # Force-accept the failed group because it did partial work
        await retry_restart_node(n0=n0, force=True, accept=True)
        return rescue["id"]
    except (HTTPStatusError, RuntimeError) as e:
        raise RuntimeError("Failed to create or retrieve new rescue group node") from e
