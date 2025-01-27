"""Utility functions for working with butler commands"""

from functools import lru_cache, partial

import yaml
from anyio import Path, to_thread
from sqlalchemy.engine import url

from lsst.daf.butler import Butler, ButlerConfig, ButlerRepoIndex
from lsst.daf.butler._exceptions import MissingCollectionError
from lsst.utils.db_auth import DbAuth

from ..config import config
from . import errors
from .logging import LOGGER

logger = LOGGER.bind(module=__name__)


BUTLER_REPO_INDEX = ButlerRepoIndex()
"""An index of all known butler repositories, as populated by the
DAF_BUTLER_REPOSITORIES environment variable.
"""


@lru_cache
async def get_butler_config(repo: str, *, without_datastore: bool = False) -> ButlerConfig:
    """Create a butler config object for a repo known to the service's
    environment.
    """

    try:
        repo_uri = BUTLER_REPO_INDEX.get_repo_uri(label=repo)
    except KeyError:
        # No such repo known to the service
        logger.warning("Butler repo %s not known to environment.", repo)
        repo_uri = repo

    try:
        bc_f = partial(
            ButlerConfig,
            other=repo_uri,
            without_datastore=without_datastore,
        )
        bc = await to_thread.run_sync(bc_f)
    except FileNotFoundError:
        # No such repo known to Butler
        logger.error("Butler repo %s not known.", repo)
        raise RuntimeError("Unknown Butler Repo %s", repo)

    try:
        db_auth_info = yaml.safe_load(await Path(config.butler.authentication_file).read_text())
    except FileNotFoundError:
        logger.error("No Butler Registry authentication secrets found.")
        # delegate db auth info discovery to normal toolchain
        return bc

    db_url = url.make_url(bc["registry"]["db"])
    db_auth = DbAuth(authList=db_auth_info).getAuth(
        dialectname=db_url.drivername,
        username=db_url.username,
        host=db_url.host,
        port=db_url.port,
        database=db_url.database,
    )

    bc[".registry.username"] = db_auth[0]
    bc[".registry.password"] = db_auth[1]
    return bc


async def remove_run_collections(
    butler_repo: str,
    collection_name: str,
    *,
    fake_reset: bool = False,
) -> None:
    """Remove a collection from Butler

    Parameters
    ----------
    butler_repo: str
        Butler Repo

    collection_name: str
        Collection to remove

    fake_reset: bool
        Allow for missing butler
    """
    fake_reset = fake_reset or config.butler.mock
    try:
        butler_f = partial(
            Butler.from_config,
            butler_repo,
            collections=[collection_name],
            without_datastore=True,
        )
        butler = await to_thread.run_sync(butler_f)
    except Exception as e:
        if fake_reset:
            return
        raise errors.CMNoButlerError(e) from e  # pragma: no cover
    try:  # pragma: no cover
        await to_thread.run_sync(butler.registry.removeCollection, collection_name)
    except MissingCollectionError:
        pass
    except Exception as msg:
        raise errors.CMButlerCallError(msg) from msg


# FIXME how is this different to `remove_run_collections`?
async def remove_non_run_collections(
    butler_repo: str,
    collection_name: str,
    *,
    fake_reset: bool = False,
) -> None:
    """Remove a collection from Butler

    Parameters
    ----------
    butler_repo: str
        Butler Repo

    collection_name: str
        Collection to remove

    fake_reset: bool
        Allow for missing butler
    """
    fake_reset = fake_reset or config.butler.mock
    try:
        butler_f = partial(
            Butler.from_config,
            butler_repo,
            collections=[collection_name],
            without_datastore=True,
        )
        butler = await to_thread.run_sync(butler_f)
    except Exception as e:
        if fake_reset:
            return
        raise errors.CMNoButlerError(e) from e  # pragma: no cover
    try:  # pragma: no cover
        await to_thread.run_sync(butler.registry.removeCollection, collection_name)
    except Exception as msg:
        raise errors.CMButlerCallError(msg) from msg


async def remove_collection_from_chain(
    butler_repo: str,
    chain_collection: str,
    collection_name: str,
    *,
    fake_reset: bool = False,
) -> None:
    """Remove a collection from a chained collection

    Parameters
    ----------
    butler_repo: str
        Butler Repo

    chain_collection: str,
        Chained collection to edit

    collection_name: str
        Collection to remove

    fake_reset: bool
        Allow for missing butler
    """
    fake_reset = fake_reset or config.butler.mock
    if fake_reset:
        return
    raise NotImplementedError


async def remove_datasets_from_collections(
    butler_repo: str,
    tagged_collection: str,
    collection_name: str,
    *,
    fake_reset: bool = False,
) -> None:
    """Remove a datasets in a collection from a TAGGED collection

    Parameters
    ----------
    butler_repo: str
        Butler Repo

    tagged_collection: str,
        Tagged collection to edit

    collection_name: str
        Collection to remove

    fake_reset: bool
        Allow for missing butler
    """
    fake_reset = fake_reset or config.butler.mock
    if fake_reset:
        return
    raise NotImplementedError
