from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

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

    from ..common.types import AnyAsyncSession

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

    fullname: Any  # Human-readable unique name for row
    id: Any  # Primary Key, typically an int
    class_string: str  # Name to use for help functions and descriptions
    col_names_for_table: list
    name: Any  # Human-readable name for row

    @classmethod
    async def get_rows[T: RowMixin](
        cls: type[T],
        session: AnyAsyncSession,
        **kwargs: Any,
    ) -> Sequence[T]:
        """Get rows associated to a particular table

        Parameters
        ----------
        session : A
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
    async def get_row[T: RowMixin](
        cls: type[T],
        session: AnyAsyncSession,
        row_id: int,
    ) -> T:
        """Get a single row, matching row.id == row_id

        Parameters
        ----------
        session : A
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
            msg = f"{cls} {row_id} not found"
            raise CMMissingIDError(msg)
        return result

    @classmethod
    async def get_row_by_name[T: RowMixin](
        cls: type[T],
        session: AnyAsyncSession,
        name: str,
    ) -> T:
        """Get a single row, with row.name == name

        Parameters
        ----------
        session : A
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
            msg = f"{cls} {name} not found"
            raise CMMissingFullnameError(msg)
        return row

    @classmethod
    async def get_row_by_fullname[T: RowMixin](
        cls: type[T],
        session: AnyAsyncSession,
        fullname: str,
    ) -> T:
        """Get a single row, with row.fullname == fullname

        Parameters
        ----------
        session : A
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
            msg = f"{cls} {fullname} not found"
            raise CMMissingFullnameError(msg)
        return row

    @classmethod
    async def delete_row(
        cls,
        session: AnyAsyncSession,
        row_id: int,
    ) -> None:
        """Delete a single row, matching row.id == row_id

        Parameters
        ----------
        session : A
            DB session manager

        row_id: int
            PrimaryKey of the row to delete

        Raises
        ------
        CMBadStateTransitionError: Row is in use (has an active status)
        """
        row = await session.get(cls, row_id)
        if row is None:
            msg = f"{cls} {row_id} not found"
            raise CMMissingIDError(msg)
        # Parentless rows are deletable irrespective of status
        if not hasattr(row, "parent_id"):
            pass
        elif hasattr(row, "status") and row.status not in DELETABLE_STATES:
            msg = f"Can not delete a row because it is in use {row.fullname} {row.status}"
            raise CMBadStateTransitionError(
                msg,
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
        session: AnyAsyncSession,
        row_id: int,
    ) -> None:
        """Hook called during delete_row

        Parameters
        ----------
        session : A
            DB session manager

        row_id: int
            PrimaryKey of the row to delete

        """
        # This may be implemented by child classes.
        logger.warning("Delete hook not implemented by class", cls=cls)
        return

    @classmethod
    async def update_row[T: RowMixin](
        cls: type[T],
        session: AnyAsyncSession,
        row_id: int,
        **kwargs: Any,
    ) -> T:
        """Update a single row, matching row.id == row_id

        Parameters
        ----------
        session : A
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
            msg = f"{cls} {row_id} not found"
            raise CMMissingIDError(msg)
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
    async def create_row[T: RowMixin](
        cls: type[T],
        session: AnyAsyncSession,
        **kwargs: Any,
    ) -> T:
        """Create a single row

        Parameters
        ----------
        session : A
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
        cls,
        session: AnyAsyncSession,
        **kwargs: Any,
    ) -> dict:
        """Get additional keywords needed to create a row

        This should be overridden by sub-classes as needed

        The default is to just return the original keywords

        Parameters
        ----------
        session : A
            DB session manager

        kwargs: Any
            Columns and associated values for the new row

        Returns
        -------
        create_kwargs: dict
            Keywords needed to create a new row
        """
        return kwargs

    async def update_values[T: RowMixin](
        self: T,
        session: AnyAsyncSession,
        **kwargs: Any,
    ) -> T:
        """Update values in a row

        Parameters
        ----------
        session : A
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
