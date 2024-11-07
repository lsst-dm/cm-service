from __future__ import annotations

import types
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.utils import doImport
from lsst.utils.introspection import get_full_type_name

from ..common.enums import StatusEnum
from ..common.errors import CMBadHandlerTypeError
from ..common.utils import add_sys_path

if TYPE_CHECKING:
    from .element import ElementMixin
    from .node import NodeMixin
    from .script import Script


class Handler:
    """Base class to handle callbacks generated by particular
    database actions.

    Each entry in the database will have an associated
    Handler and specification fragment, which will be used
    where particular database actions are taken.
    """

    handler_cache: ClassVar[dict[int, Handler]] = {}

    plugin_dir: str | None = None
    config_dir: str | None = None

    def __init__(self, spec_block_id: int, **kwargs: dict) -> None:
        self._spec_block_id = spec_block_id
        self._data = kwargs.copy()

    @classmethod
    def reset_cache(cls) -> None:
        cls.handler_cache = {}

    @classmethod
    def remove_from_cache(
        cls,
        spec_block_id: int,
    ) -> None:
        cls.handler_cache.pop(spec_block_id, None)

    @staticmethod
    def get_handler(
        spec_block_id: int,
        class_name: str,
        **kwargs: dict,
    ) -> Handler:
        """Create and return a handler

        Parameters
        ----------
        spec_block_id: int
            Id for the associated SpecBlock

        class_name : str
            Name of the handler class requested

        Returns
        -------
        handler : Handler
            Requested handler

        Notes
        -----
        The handlers are cached by spec_block_id
        If a cached handler is found that will be returned
        instead of producing a new one.
        """
        cached_handler = Handler.handler_cache.get(spec_block_id)
        if cached_handler is None:
            with add_sys_path(Handler.plugin_dir):
                handler_class = doImport(class_name)
            if isinstance(handler_class, types.ModuleType):  # pragma: no cover
                raise CMBadHandlerTypeError(f"{type(handler_class)} is a Module, not a handler class")
            cached_handler = handler_class(spec_block_id, **kwargs)
            Handler.handler_cache[spec_block_id] = cached_handler
        return cached_handler

    @property
    def data(self) -> dict[str, Any]:
        """Return the handler's data"""
        return self._data

    def get_handler_class_name(self) -> str:
        """Return this class's full name"""
        return get_full_type_name(self)

    async def process(
        self,
        session: async_scoped_session,
        node: NodeMixin,
        **kwargs: Any,
    ) -> tuple[bool, StatusEnum]:
        """Process a `Node` as much as possible

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        node: NodeMixin
            The `Node` in question

        kwargs: Any
            Used to override processing configuration

        Returns
        -------
        changed : bool
            True if anything has changed
        status : StatusEnum
            Status of the processing
        """
        raise NotImplementedError(f"{type(self)}.process")

    async def run_check(
        self,
        session: async_scoped_session,
        node: NodeMixin,
        **kwargs: Any,
    ) -> tuple[bool, StatusEnum]:
        """Check on a Nodes's status

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        node: NodeMixin
            The `Node` in question

        kwargs: Any
            Used to override processing configuration

        Returns
        -------
        changed : bool
            True if anything has changed
        status : StatusEnum
            Status of the processing
        """
        raise NotImplementedError(f"{type(self)}.run_check")

    async def reset(
        self,
        session: async_scoped_session,
        node: NodeMixin,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> StatusEnum:
        """Reset a `Node` to an earlier status

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        node: NodeMixin
            The `Node` in question

        to_status: StatusEnum
            Status to reset the node to

        fake_reset: bool
            Don't actually try to remove collections if True

        Returns
        -------
        status : StatusEnum
            Status of the processing
        """
        raise NotImplementedError(f"{type(self)}.reset")

    async def reset_script(
        self,
        session: async_scoped_session,
        node: NodeMixin,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> StatusEnum:
        """Reset a `Node` to an earlier status

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        node: NodeMixin
            The `Node` in question

        to_status: StatusEnum
            Status to reset the node to

        fake_reset: bool
            Don't actually try to remove collections if True

        Returns
        -------
        status : StatusEnum
            Status of the processing
        """
        raise NotImplementedError(f"{type(self)}.reset_script")

    async def review(
        self,
        session: async_scoped_session,
        element: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        """Review an `Element`

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        element: ElementMixin
            The `Element` in question

        Returns
        -------
        status : StatusEnum
            Status of the processing
        """
        raise NotImplementedError(f"{type(self)}.review")

    async def review_script(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        """Review a `Script`

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        script: Script
            The `Script` in question

        parent: ElementMixin
            Parent `Node` from script

        Returns
        -------
        status : StatusEnum
            Status of the processing
        """
        raise NotImplementedError(f"{type(self)}.review_script")
