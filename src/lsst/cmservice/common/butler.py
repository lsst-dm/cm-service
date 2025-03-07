"""Module in support of working with Butlers.

A CM Service that has a configured ``BUTLER_REPO_INDEX`` should provide a
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
from functools import cache, cached_property, partial
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from anyio import to_thread
from sqlalchemy.engine import url

from lsst.daf.butler import Butler, ButlerConfig, ButlerRepoIndex
from lsst.daf.butler._exceptions import MissingCollectionError
from lsst.daf.butler.direct_butler import DirectButler
from lsst.daf.butler.registry import CollectionArgType
from lsst.resources import ResourcePathExpression
from lsst.utils.db_auth import DbAuth, DbAuthError

from ..config import config
from . import errors
from .logging import LOGGER

logger = LOGGER.bind(module=__name__)


BUTLER_REPO_INDEX = ButlerRepoIndex()
"""An index of all known butler repositories, as populated by the
DAF_BUTLER_REPOSITORIES environment variable.
"""


class ButlerFactory:
    """When created, the LabeledButlerFactory will create an instance of each
    Butler known to the application configuration. This occurs synchronously
    so it is best performed at application startup. After initializing, the
    factory can hand out ``clone()`` copies of available Butlers.
    """

    def __init__(self) -> None:
        """Initialize a butler factory by creating butler pool instances for
        each known repository.
        """
        # forced property lookup; cache the registry auth file contents
        _ = self.butler_auth_config

        # create and cache any butler factories known to the service
        for label in BUTLER_REPO_INDEX.get_known_repos():
            _ = self.get_butler_factory(label)
        return None

    @cached_property
    def butler_auth_config(self) -> list[dict[str, str]] | None:
        """Read a butler authentication file for secrets.

        Notes
        -----
        This is a `functools.cached_property` that is meant to be first access
        during instance initialization so any IO is performed synchronously
        at application startup and cached for the lifetime of the object and/or
        the application.
        """
        try:
            # FIXME ought to validate the loaded value against expectations
            return yaml.safe_load(Path(config.butler.authentication_file).read_text())
        except FileNotFoundError:
            logger.warning("No Butler Registry authentication secrets file found.")
            # delegate db auth info discovery to normal toolchain
            return None

    def get_butler(self, label: str, collections: list[str] | None = None) -> Butler | None:
        """Get a butler clone from the factory.

        Notes
        -----
        This is the primary public interface to the factory object.
        """
        factory = self.get_butler_factory(label)
        if factory is None:
            return None
        return factory(collections=collections)

    @cache
    def get_butler_factory(self, label: str) -> Callable[..., Butler] | None:
        """Return a factory function that creates a butler clone.

        Notes
        -----
        This method is backed by a `functools.cache`, a threadsafe cache.
        """
        try:
            _butler_config = self.get_butler_config(label=label)
            _butler = Butler.from_config(_butler_config)
            if TYPE_CHECKING:
                assert isinstance(_butler, DirectButler)
            _butler._preload_cache(load_dimension_record_cache=False)
        except KeyError:
            return None

        def factory(collections: CollectionArgType) -> Butler:
            return _butler.clone(collections=collections)

        return factory

    def update_butler_url(self, bc: ButlerConfig) -> ButlerConfig:
        """Update a butler config with registry secrets.

        Returns
        -------
        ``ButlerConfig``
            The same configuration object passed as input is returned, with
            secrets applied or not, depending on whether secrets were available
            for the input config's registry URL.

        Notes
        -----
        This method makes use of the cached ``butler_auth_config`` property
        which contains the set of butler registry secrets known to the service.
        Missing secrets may produce non-working Butlers, but not all butlers
        have associated secrets, so failure to locate a secret is not an error.
        """
        if self.butler_auth_config is None:
            return bc

        db_url = url.make_url(bc["registry"]["db"])
        try:
            db_auth = DbAuth(authList=self.butler_auth_config).getAuth(
                dialectname=db_url.drivername,
                username=db_url.username,
                host=db_url.host,
                port=db_url.port,
                database=db_url.database,
            )
            bc[".registry.username"] = db_auth[0]
            bc[".registry.password"] = db_auth[1]
        except DbAuthError as e:
            logger.warning(f"Could not parse db auth from provided url[{db_url}]: {e}")
        return bc

    def get_butler_config(self, label: str, *, without_datastore: bool = True) -> ButlerConfig:
        """Create a butler config object for a repo known to the service's
        environment.
        """

        try:
            repo_uri: ResourcePathExpression = BUTLER_REPO_INDEX.get_repo_uri(label=label)
        except KeyError:
            logger.warning("Butler repo %s not known to environment.", label)
            repo_uri = label

        try:
            bc_f = partial(
                ButlerConfig,
                other=repo_uri,
                without_datastore=without_datastore,
            )
            bc = bc_f()
        except FileNotFoundError:
            logger.error("Butler repo %s not known.", label)
            raise RuntimeError("Unknown Butler Repo %s", label)

        # Any generated Butler config is hydrated with application secrets via
        # this tail call.
        return self.update_butler_url(bc)


BUTLER_FACTORY = ButlerFactory()
"""A module level butler factory created at module import, available for use
in other modules.
"""


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
