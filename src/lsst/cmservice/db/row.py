from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_scoped_session

from ..common.enums import StatusEnum
from ..common.errors import (
    CMBadStateTransitionError,
    CMIDMismatchError,
    CMIntegrityError,
    CMMissingFullnameError,
    CMMissingIDError,
)
from ..common.logging import LOGGER

logger = LOGGER.bind(module=__name__)

if TYPE_CHECKING:
    from collections.abc import Sequence

    T = TypeVar("T", bound="RowMixin")
    A = TypeVar("A", AsyncSession, async_scoped_session)

DELETABLE_STATES = [
    StatusEnum.failed,
    StatusEnum.rejected,
    StatusEnum.waiting,
    StatusEnum.ready,
]


class RowMixin:
    """Mixin class to define common features of database rows for all tables.

    Defines an interface to manipulate any sort of table.
    """

    id: Any  # Primary Key, typically an int
    name: Any  # Human-readable name for row
    fullname: Any  # Human-readable unique name for row

    class_string: str  # Name to use for help functions and descriptions

    @classmethod
    async def get_rows(
        cls: type[T],
        session: async_scoped_session,
        **kwargs: Any,
    ) -> Sequence[T]:
        """Get rows associated to a particular table

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Keywords
        --------
        parent_id: int | None
            If provided, used to limit search results

        parent_name: str | None
            If provided, used to limit search results

        parent_class: type | None
            If provided, used to limit search results

        skip: int
            Number of rows to skip before returning results

        limit: int
            Number of row to return

        Returns
        -------
        results: Sequence[T]
            All the matching rows
        """
        skip = kwargs.get("skip", 0)
        limit = kwargs.get("limit", 100)
        parent_id = kwargs.get("parent_id")
        parent_name = kwargs.get("parent_name")
        parent_class = kwargs.get("parent_class")

        q = select(cls)
        if hasattr(cls, "parent_id"):
            # FIXME All of these tests assert that parent_class is not None
            #       otherwise it would raise an AttributeError; the constraint
            #       might as well be satisfied by the first id matching without
            #       also evaluating additional options. If the gimmick is that
            #       the method can be invoked with one of parent_id, _name, or
            #       the parent class, it is invalidated by the fact that
            #       parent_class is used in all three cases, so defining any of
            #       the others adds no value.
            if TYPE_CHECKING:
                assert parent_class is not None
            if parent_class is not None:
                parent_id_ = getattr(cls, "parent_id")
                q = q.where(parent_class.id == parent_id_)
            if parent_name is not None:
                q = q.where(parent_class.fullname == parent_name)
            if parent_id is not None:
                q = q.where(parent_class.id == parent_id)
        q = q.offset(skip).limit(limit)
        results = await session.scalars(q)
        return results.all()

    @classmethod
    async def get_row(
        cls: type[T],
        session: A,
        row_id: int,
    ) -> T:
        """Get a single row, matching row.id == row_id

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        row_id: int
            PrimaryKey of the row to return

        Returns
        -------
        results: T
            The matching row
        """
        result = await session.get(cls, row_id)
        if result is None:
            raise CMMissingIDError(f"{cls} {row_id} not found")
        return result

    @classmethod
    async def get_row_by_name(
        cls: type[T],
        session: async_scoped_session,
        name: str,
    ) -> T:
        """Get a single row, with row.name == name

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        name : str
            name of the row to return

        Returns
        -------
        result: T
            Matching row
        """
        query = select(cls).where(cls.name == name)
        rows = await session.scalars(query)
        row = rows.first()
        if row is None:
            raise CMMissingFullnameError(f"{cls} {name} not found")
        return row

    @classmethod
    async def get_row_by_fullname(
        cls: type[T],
        session: async_scoped_session,
        fullname: str,
    ) -> T:
        """Get a single row, with row.fullname == fullname

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        fullname : str
            Full name of the row to return

        Returns
        -------
        result: T
            Matching row
        """
        query = select(cls).where(cls.fullname == fullname)
        rows = await session.scalars(query)
        row = rows.first()
        if row is None:
            raise CMMissingFullnameError(f"{cls} {fullname} not found")
        return row

    @classmethod
    async def delete_row(
        cls,
        session: async_scoped_session,
        row_id: int,
    ) -> None:
        """Delete a single row, matching row.id == row_id

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        row_id: int
            PrimaryKey of the row to delete

        Raises
        ------
        CMBadStateTransitionError: Row is in use (has an active status)
        """
        row = await session.get(cls, row_id)
        if row is None:
            raise CMMissingIDError(f"{cls} {row_id} not found")
        # Parentless rows are deletable irrespective of status
        if not hasattr(row, "parent_id"):
            pass
        elif hasattr(row, "status") and row.status not in DELETABLE_STATES:
            raise CMBadStateTransitionError(
                f"Can not delete a row because it is in use {row.fullname} {row.status}",
            )
        try:
            await session.delete(row)
        except IntegrityError as msg:
            if TYPE_CHECKING:
                assert msg.orig  # for mypy
            raise CMIntegrityError(params=msg.params, orig=msg.orig, statement=msg.statement) from msg
        await cls._delete_hook(session, row_id)

    @classmethod
    async def _delete_hook(
        cls,
        session: async_scoped_session,
        row_id: int,
    ) -> None:
        """Hook called during delete_row

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        row_id: int
            PrimaryKey of the row to delete

        """
        # This may be implemented by child classes.
        logger.warning(f"Delete hook not implemented by {cls}")
        return

    @classmethod
    async def update_row(
        cls: type[T],
        session: async_scoped_session,
        row_id: int,
        **kwargs: Any,
    ) -> T:
        """Update a single row, matching row.id == row_id

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        row_id: int
            PrimaryKey of the row to return

        kwargs: Any
            Columns and associated new values

        Returns
        -------
        result: RowMixin
            Updated row

        Raises
        ------
        CMIDMismatchError : ID mismatch between row IDs

        CMMissingFullnameError : Could not find row

        CMIntegrityError : catching a IntegrityError
        """
        if kwargs.get("id", row_id) != row_id:
            raise CMIDMismatchError("ID mismatch between URL and body")
        row = await session.get(cls, row_id)
        if row is None:
            raise CMMissingIDError(f"{cls} {row_id} not found")
        async with session.begin_nested():
            try:
                for var, value in kwargs.items():
                    if not value:
                        continue
                    if isinstance(value, dict):
                        the_dict = getattr(row, var).copy()
                        the_dict.update(**value)
                        setattr(row, var, the_dict)
                    else:
                        setattr(row, var, value)
            except IntegrityError as msg:
                await session.rollback()
                if TYPE_CHECKING:
                    assert msg.orig  # for mypy
                raise CMIntegrityError(
                    params=msg.params,
                    orig=msg.orig,
                    statement=msg.statement,
                ) from msg
        await session.refresh(row)
        return row

    @classmethod
    async def create_row(
        cls: type[T],
        session: async_scoped_session,
        **kwargs: Any,
    ) -> T:
        """Create a single row

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        kwargs: Any
            Columns and associated values for the new row

        Returns
        -------
        result: RowMixin
            Newly created row
        """
        create_kwargs = await cls.get_create_kwargs(session, **kwargs)
        row = cls(**create_kwargs)
        async with session.begin_nested():
            try:
                session.add(row)
            except IntegrityError as msg:
                await session.rollback()
                if TYPE_CHECKING:
                    assert msg.orig  # for mypy
                raise CMIntegrityError(params=msg.params, orig=msg.orig, statement=msg.statement) from msg
        await session.refresh(row)
        return row

    @classmethod
    async def get_create_kwargs(
        cls: type[T],
        session: async_scoped_session,
        **kwargs: Any,
    ) -> dict:
        """Get additional keywords needed to create a row

        This should be overridden by sub-classes as needed

        The default is to just return the original keywords

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        kwargs: Any
            Columns and associated values for the new row

        Returns
        -------
        create_kwargs: dict
            Keywords needed to create a new row
        """
        return kwargs

    async def update_values(
        self: T,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> T:
        """Update values in a row

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        kwargs: Any
            Columns and associated new values

        Returns
        -------
        result: RowMixin
            Updated row

        Raises
        ------
        CMIntegrityError : Catching a IntegrityError
        """
        try:
            async with session.begin_nested():
                for var, value in kwargs.items():
                    setattr(self, var, value)
            await session.refresh(self)
        except IntegrityError as msg:
            await session.rollback()
            if TYPE_CHECKING:
                assert msg.orig
            raise CMIntegrityError(params=msg.params, orig=msg.orig, statement=msg.statement) from msg
        return self
