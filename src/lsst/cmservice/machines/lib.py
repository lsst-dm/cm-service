"""Library functions supporting State Machines"""

from collections import ChainMap
from collections.abc import Callable, Generator
from functools import partial, reduce
from shutil import rmtree
from typing import Any
from uuid import uuid5

from anyio import Path, to_thread
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import col, select

from lsst.cmservice.models.db.campaigns import ActivityLog, Campaign, Manifest, Node
from lsst.cmservice.models.enums import DEFAULT_NAMESPACE, ManifestKind
from lsst.cmservice.models.lib.logging import LOGGER
from lsst.cmservice.models.lib.timestamp import element_time, now_utc
from lsst.cmservice.models.types import AsyncSession

logger = LOGGER.bind(module=__name__)


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


async def deltree(path: Path) -> None:
    """Async wrapper for the `shutil.rmtree` function with error callback."""

    errors: list[tuple[Path, BaseException]] = []

    def error_cb(func: Callable[..., Any], path: str, e: BaseException) -> None:
        """Exception handler callback from `shutil.rmtree`."""
        errors.append((Path(path), e))

    # Ensure that the passed path is actually an anyio.Path
    _path = Path(path)

    if await _path.exists():
        _deltree = partial(rmtree, _path, onexc=error_cb)
        await to_thread.run_sync(_deltree)
    else:
        logger.warning("Asked to delete path that doesn't exist.", path=str(path))

    # Check for errors and log them individually.
    # The last best recovery action if we can't delete the entire tree is to
    # try to rename it instead.
    if errors:
        for e_path, exc in errors:
            logger.error("Failed to remove file object", path=e_path, exc=exc)
        try:
            legacy_dir = _path.with_stem(f".{element_time()}")
            await _path.replace(legacy_dir)
            logger.warning("Moved target directory to legacy path", path=path, legacy_dir=str(legacy_dir))
        except Exception as e:
            logger.error("Error raised trying to rename directory", path=path, exc=e)
            # pragma: human intervention required
            raise
