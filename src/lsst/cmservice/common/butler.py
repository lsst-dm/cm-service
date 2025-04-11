"""Module in support of working with Butlers.

A CM Service that has a configured ``BUTLER_REPO_INDEX`` provides a
factory function that manages a pool of Butler instances for each of these
repos. This factory function is inspired by the
`lsst.daf.butler.LabeledButlerFactory` and provides ``clone()`` instances of
available Butlers when asked to provide one.

Notes
-----
The butler "factory" follows a "global" pattern where it is assigned to
a module-level variable at import-time. Other modules can import this factory
and use it to produce on-demand butler clones. It is not necessary to use a
butler factory as an injected dependency when using this pattern, but this
module should be imported as early as possible in the application startup;
it does not depend on a running event loop.
"""

from collections.abc import Callable
from functools import cache, partial
from typing import TYPE_CHECKING

from anyio import to_thread
from botocore.exceptions import ClientError
from sqlalchemy.exc import OperationalError

from lsst.daf.butler import Butler, ButlerConfig, ButlerRepoIndex, MissingCollectionError
from lsst.daf.butler.direct_butler import DirectButler
from lsst.daf.butler.registry import CollectionArgType, RegistryConfig
from lsst.resources import ResourcePathExpression

from ..config import config
from . import errors
from .logging import LOGGER

logger = LOGGER.bind(module=__name__)


BUTLER_REPO_INDEX = ButlerRepoIndex()
"""An index of all known butler repositories, as populated by the
``DAF_BUTLER_REPOSITORIES`` environment variable.
"""


class ButlerFactory:
    """The ButlerFactory will create an instance of each Butler known to the
    application during initialization. This occurs synchronously so it is best
    performed at application startup. After initializing, the factory can hand
    out ``clone()`` copies of available Butlers.
    """

    def __init__(self) -> None:
        """Initialize a ButlerFactory by creating butler pool instances for
        each known repository.
        """
        # create and cache any butler factories known to the service
        for label in BUTLER_REPO_INDEX.get_known_repos():
            if config.butler.eager:
                _ = self.get_butler_factory(label)

    def get_butler(self, label: str, collections: list[str] | None = None) -> Butler | None:
        """Get a butler clone from the factory with the specified collections
        constraint applied.

        Notes
        -----
        This is the primary public interface to the factory object.
        """
        factory = self.get_butler_factory(label)
        if factory is None:
            return None
        return factory(collections=collections)

    async def aget_butler(self, label: str, collections: list[str] | None = None) -> Butler | None:
        """Asynchronous version of the `get_butler` method, which invokes the
        factory from a worker thread.
        """

        get_factory_f = partial(self.get_butler_factory, label=label)
        factory = await to_thread.run_sync(get_factory_f)
        if factory is None:
            return None
        factory_f = partial(factory, collections=collections)
        return await to_thread.run_sync(factory_f)

    @cache
    def get_butler_factory(
        self, label: str, *, without_datastore: bool = True
    ) -> Callable[..., Butler] | None:
        """Return a factory function that creates a butler clone.

        Notes
        -----
        This method is backed by a `functools.cache`, a threadsafe cache.

        If the return value is None, the service could not create a Butler for
        the desired label or no such Butler is configured. In the former case,
        the service log should include exception information related to the
        failed Butler creation.

        If the application's Butler ``eager`` parameter is set, the Factory
        instance instantiates all known Butlers at initialization. If this
        parameter is false, then calling this method the first time will block
        until the requested Butler is ready.

        Returns
        -------
        `lsst.daf.butler` or `None`
            A cloned instance of a ``Butler`` or None if the labelled Butler
            could not be created from the configuration inputs.
        """
        try:
            _butler_config = self.get_butler_config(label=label)
            _butler = Butler.from_config(_butler_config, without_datastore=without_datastore)
            if TYPE_CHECKING:
                assert isinstance(_butler, DirectButler)
            _butler._preload_cache(load_dimension_record_cache=False)
        except (ClientError, OperationalError, RuntimeError):
            # Case that configured butler could not be created because of an
            # S3 or database error, or other Runtime error
            logger.exception()
            return None
        except KeyError:
            # Case that no such butler was configured
            logger.warning("No such butler configured: %s", label)
            return None

        def factory(collections: CollectionArgType) -> Butler:
            return _butler.clone(collections=collections)

        return factory

    @cache
    def get_butler_config(self, label: str, *, without_datastore: bool = True) -> ButlerConfig:
        """Create a butler config object for a repo known to the service's
        environment.

        Returns
        -------
        ``lsst.daf.butler.ButlerConfig``
        """

        try:
            repo_uri: ResourcePathExpression = BUTLER_REPO_INDEX.get_repo_uri(label=label)
        except KeyError:
            logger.warning("Butler repo %s not known to environment.", label)
            repo_uri = label

        try:
            bc = ButlerConfig(other=repo_uri, without_datastore=without_datastore)
        except FileNotFoundError:
            logger.error("Butler repo %s not known.", label)
            raise RuntimeError("Unknown Butler Repo %s", label)
        return bc

    @cache
    def get_butler_registry_config(self, label: str) -> RegistryConfig:
        """Fetch the Registry Config for a Butler by label.

        Registry
        --------
        ``lsst.daf.butler.registry.RegistryConfig``

        Raises
        ------
        RuntimeError
            Raised when the Butler config constructor has an issue, such as
            failure to import a package.
        """
        return RegistryConfig(self.get_butler_config(label=label))


BUTLER_FACTORY = ButlerFactory()
"""A module level butler factory created at module import, available for use
in other modules.
"""


# TODO: deprecate these functions that attempt to "remove" data from Butlers.
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
