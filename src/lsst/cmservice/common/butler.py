"""Utility functions for working with butler commands"""

from lsst.daf.butler import Butler


def remove_run_collections(butler_repo: str, collection_name: str) -> None:
    """Remove a collection from Butler

    Parameters
    ----------
    butler_repo: str
        Butler Repo

    collection_name: str
        Collection to remove
    """
    butler = Butler.from_config(butler_repo, collections=[collection_name], without_datastore=True)
    try:
        butler.registry.removeCollection(collection_name)
    except Exception as msg:  # pylint: disable=broad-exception-caught
        print(f"Caught exception {msg} when removing run collection")


def remove_non_run_collections(butler_repo: str, collection_name: str) -> None:
    """Remove a collection from Butler

    Parameters
    ----------
    butler_repo: str
        Butler Repo

    collection_name: str
        Collection to remove
    """
    butler = Butler.from_config(butler_repo, collections=[collection_name], without_datastore=True)
    try:
        butler.registry.removeCollection(collection_name)
    except Exception as msg:  # pylint: disable=broad-exception-caught
        print(f"Caught exception {msg} when removing non-run collection")


def remove_collection_from_chain(
    butler_repo: str,
    chain_collection: str,
    collection_name: str,
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
    """
    raise NotImplementedError


def remove_datasets_from_collections(
    butler_repo: str,
    tagged_collection: str,
    collection_name: str,
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
    """
    raise NotImplementedError
