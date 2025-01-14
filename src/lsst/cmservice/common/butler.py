"""Utility functions for working with butler commands"""

from functools import partial

from anyio import to_thread

from lsst.daf.butler import Butler, MissingCollectionError

from ..common import errors


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
    if fake_reset:
        return
    raise NotImplementedError
