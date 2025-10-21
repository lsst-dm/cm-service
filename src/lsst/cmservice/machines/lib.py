"""Library functions supporting State Machines"""

import re
from collections import ChainMap
from collections.abc import Generator
from functools import reduce
from typing import Any
from uuid import uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import col, select

from ..common.enums import DEFAULT_NAMESPACE, ManifestKind
from ..common.timestamp import now_utc
from ..common.types import AsyncSession
from ..db.campaigns_v2 import ActivityLog, Campaign, Manifest, Node


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


async def materialize_activity_log(
    session: AsyncSession,
    activity_log_entry: ActivityLog,
    milestone: str,
    detail: dict | None = None,
    metadata: dict | None = None,
) -> None:
    """Given an ad-hoc, activity log entry, finalize it and materialize it.

    The provided activity log entry should not already be in the session but it
    must have a Node ID defined.
    """
    if activity_log_entry in session or activity_log_entry.node is None:
        return
    if detail is not None:
        activity_log_entry.detail = detail

    metadata = metadata or {}
    metadata["milestone"] = milestone
    activity_log_entry.metadata_ = metadata

    # A deterministic but unique ID for the log entry is formed from the event
    # "milestone" within the Node's ID namespace.
    activity_log_entry.id = uuid5(activity_log_entry.node, milestone)
    activity_log_entry.finished_at = now_utc()
    statement = (
        insert(activity_log_entry.__table__)  # type: ignore[attr-defined]
        .values(**activity_log_entry.model_dump(by_alias=True))
        .on_conflict_do_nothing()
    )
    await session.exec(statement)
    await session.commit()


def ordinal_group_nonce() -> Generator[str]:
    """Generator that yields a 0-padded ordinal number as a group nonce"""
    n = 1
    while True:
        yield f"{n:03d}"
        n += 1


async def select_manifest_by_label(
    session: AsyncSession, kind: ManifestKind, selectors: dict[str, str]
) -> Manifest | None:
    """Locate and return a single manifest of the given kind by using the
    selectors to match labels. Except when "version" is one of the selectors,
    the latest version is returned when there are multiple matches.

    The ``selectors`` parameter is a mapping of a label name to its value, such
    that ``{"versionSelector": 5}`` would match a manifest with
    ``{"version": 5}``.

    Because "labelSelectors" are always camelCase, the selector name is split
    such that the lower-case string part is the desired label. This is achieved
    by splitting the "labelSelector" at lower-to-upper-case transitions, so
    labels themselves could be camelCased, e.g., "availableCoresSelector" would
    select an "availableCores" label.

    Notes
    -----
    All provided selectors must match labels; there is no "close enough" or
    "best effort" Manifest returned if the given selectors cannot be satisfied.
    In this case the function returns a None and the caller should react in a
    sensible manner.
    """
    labels: list[tuple[str, str]] = []
    for selector, value in selectors.items():
        _label = re.findall(r"[A-Z][a-z]*|[a-z]+", selector)
        labels.append(("".join(_label[:-1]), value))

    # If the selectors are not valid
    if not len(labels):
        return None

    # Build a select statement for locating manifests with metadata labels
    # matching the selectors
    s = select(Manifest)
    for label in labels:
        s = s.where(Manifest.metadata_["labels"] == "")
    return None
