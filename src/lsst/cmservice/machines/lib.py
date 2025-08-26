"""Library functions supporting State Machines"""

from collections import ChainMap
from functools import reduce
from typing import Any

from sqlmodel import col, or_, select

from ..common.enums import DEFAULT_NAMESPACE, ManifestKind
from ..common.types import AsyncSession
from ..db.campaigns_v2 import Campaign, Manifest, Node


async def assemble_config_chain(
    session: AsyncSession,
    node: Campaign | Node,
    extra: dict[str, dict] = {},
) -> dict[str, ChainMap]:
    """Assembles a configuration chain for the specified node.

    The standard configuration chain lookup is
    - The node's direct configuration
    - (The node's incoming edge configuration)
    - A campaign manifest of the specified kind (optional)
    - Any extra manifest configuration provided at runtime

    Returns
    -------
    dict
        A mapping of configuration manifest names to a ChainMap for that type
        of manifest.
    """
    if isinstance(node, Campaign):
        raise NotImplementedError("Config Chains should be assembled only for Nodes")

    config_chain: dict[str, ChainMap] = {}
    # FIXME this should not iterate the node's configuration, it should iterate
    # the types of manifests
    for kind in ManifestKind.__members__:
        # each key in the node configuration is the basis of a configchain
        # find the "latest" manifest of this kind within the campaign
        campaign_config: dict[str, Any] = {}

        s = (
            select(Manifest)
            .where(or_(Manifest.namespace == node.namespace, Manifest.namespace == DEFAULT_NAMESPACE))
            .where(col(Manifest.kind) == kind)
            .order_by(col(Manifest.version).desc())
            .limit(1)
        )
        if (manifest := (await session.exec(s)).one_or_none()) is not None:
            campaign_config = manifest.spec

        config_chain[kind] = ChainMap(
            node.configuration.get(kind, {}),
            campaign_config,
            extra.get(kind, {}),
        )
    return config_chain


def flatten_chainmap(chain: ChainMap) -> dict:
    """Flattens a ChainMap to a single dictionary.

    This function iterates the ChainMap's list of maps in reverse, i.e., from
    last to first in lookup order, and updates an accumulator dictionary with
    each one.

    Returns
    -------
    dict
        The flattened accumulator dictionary.
    """
    return reduce(lambda a, d: a.update(d) or a, reversed(chain.maps), {})
