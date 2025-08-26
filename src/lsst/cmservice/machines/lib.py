"""Library functions supporting State Machines"""

from collections import ChainMap

from sqlmodel import col, or_, select

from ..common.enums import DEFAULT_NAMESPACE, ManifestKind
from ..common.types import AsyncSession
from ..db.campaigns_v2 import Manifest, Node


async def assemble_config_chain(
    session: AsyncSession,
    node: Node,
    manifest_kind: ManifestKind | None = None,
    extra: list[dict] | None = None,
) -> ChainMap:
    """Assembles a configuration chain for the specified node.

    The standard configuration chain lookup is
    - The node's direct configuration
    - (The node's incoming edge configuration)
    - A campaign manifest of the specified kind (optional)
    """
    configuration_sources: list[dict] = [node.configuration]

    if manifest_kind is not None:
        # find the "latest" manifest of this kind within the campaign
        s = (
            select(Manifest)
            .where(or_(Manifest.namespace == node.namespace, Manifest.namespace == DEFAULT_NAMESPACE))
            .where(Manifest.kind == manifest_kind)
            .order_by(col(Manifest.version).desc())
            .limit(1)
        )
        if (manifest := (await session.exec(s)).one_or_none()) is not None:
            configuration_sources.append({manifest_kind.name.lower(): manifest.spec})

    if extra is not None:
        configuration_sources.extend(extra)
    return ChainMap(*configuration_sources)
