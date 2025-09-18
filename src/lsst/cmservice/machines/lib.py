"""Library functions supporting State Machines"""

from collections import ChainMap
from functools import reduce
from typing import Any

from sqlmodel import col, select

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
    - A library (version 0) manifest of the specified kind (optional)

    Returns
    -------
    dict
        A mapping of configuration manifest names to a ChainMap for that type
        of manifest.
    """
    if isinstance(node, Campaign):
        raise NotImplementedError("Config Chains should be assembled only for Nodes")

    config_chain: dict[str, ChainMap] = {}

    # TODO if the Node or Campaign has a selector in its spec, use those
    # instructions in the ORM where clause to match manifest metadata labels
    # TODO if manifest selection is ambiguous (i.e, more than one matching
    # manifest is found), this should be an error. IOW, remove the limit(1)
    # clause and allow the node to fail if <exec>.one_or_none() raises an
    # exception. The exception to this is ambiguity in the library manifest
    # namespace: if a campaign-scoped manifest is found, ambiguity in the
    # default namespace should result in no library manifest used in the config
    # chain; failure on ambiguous manifest for library manifests should only
    # result when no namespace-scoped manifest candidate is available.
    for kind in ManifestKind.__members__:
        # each key in the node configuration is the basis of a configchain
        # find the "latest" manifest of this kind within the campaign
        campaign_config: dict[str, Any] = {}

        s = (
            select(Manifest)
            .where(Manifest.namespace == node.namespace)
            .where(col(Manifest.kind) == kind)
            .order_by(col(Manifest.version).desc())
            .limit(1)
        )
        if (manifest := (await session.exec(s)).one_or_none()) is not None:
            campaign_config = manifest.spec
        else:
            campaign_config = {}
        s = (
            select(Manifest)
            .where(Manifest.namespace == DEFAULT_NAMESPACE)
            .where(col(Manifest.kind) == kind)
            .where(col(Manifest.version) == 0)
            .limit(1)
        )
        if (manifest := (await session.exec(s)).one_or_none()) is not None:
            library_config = manifest.spec
        else:
            library_config = {}

        config_chain[kind] = ChainMap(
            node.configuration.get(kind, {}),
            campaign_config,
            library_config,
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
