"""Utility functions for working with butler commands"""

from lsst.cmservice.common import errors
from lsst.daf.butler import Butler


def remove_run_collections(
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
        butler = Butler.from_config(butler_repo, collections=[collection_name], without_datastore=True)
    except Exception as msg:
        if fake_reset:
            return
        raise errors.CMNoButlerError(msg) from msg  # pragma: no cover
    try:  # pragma: no cover
        butler.registry.removeCollection(collection_name)
    except Exception as msg:  # pragma: no cover
        raise errors.CMButlerCallError(msg) from msg


def remove_non_run_collections(
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
        butler = Butler.from_config(butler_repo, collections=[collection_name], without_datastore=True)
    except Exception as msg:
        if fake_reset:
            return
        raise errors.CMNoButlerError(msg) from msg  # pragma: no cover
    try:  # pragma: no cover
        butler.registry.removeCollection(collection_name)
    except Exception as msg:  # pragma: no cover
        raise errors.CMButlerCallError(msg) from msg


def remove_collection_from_chain(
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


def remove_datasets_from_collections(
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
