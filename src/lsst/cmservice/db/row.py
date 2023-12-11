from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, TypeVar

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_scoped_session

from ..common.enums import StatusEnum

T = TypeVar("T")

DELETEABLE_STATES = [
    StatusEnum.failed,
    StatusEnum.rejected,
    StatusEnum.waiting,
    StatusEnum.ready,
]


class RowMixin:
    """Mixin class to define common features of database rows
    for all the tables we use in CM

    Here we a just defining the interface to manipulate
    an sort of table.
    """

    id: Any  # Primary Key, typically an int
    fullname: Any  # Human-readable name for row

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
        if parent_name is not None and parent_class is not None:
            parent_id = (await parent_class.get_row_by_fullname(session, parent_name)).id
        if parent_id is not None and parent_class is not None:
            q = q.where(parent_class.id == parent_id)
        q = q.offset(skip).limit(limit)
        async with session.begin_nested():
            results = await session.scalars(q)
            return results.all()

    @classmethod
    async def get_row(
        cls: type[T],
        session: async_scoped_session,
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
        async with session.begin_nested():
            result = await session.get(cls, row_id)
            if result is None:
                raise HTTPException(status_code=404, detail=f"{cls} {row_id} not found")
            return result

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
        # This is a stupid workaround to fool mypy
        cls_copy = cls
        if TYPE_CHECKING:
            assert issubclass(cls_copy, RowMixin)
        query = select(cls).where(cls_copy.fullname == fullname)
        async with session.begin_nested():
            rows = await session.scalars(query)
            row = rows.first()
            if row is None:
                raise HTTPException(status_code=404, detail=f"{cls} {fullname} not found")
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
        """
        async with session.begin_nested():
            row = await session.get(cls, row_id)
            if row is not None:
                if hasattr(row, "status") and row.status not in DELETEABLE_STATES:
                    raise ValueError(f"Can not delete a row because it is in use {row} {row.status}")
                await session.delete(row)

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
        HTTPException : Code 400, ID mismatch between row IDs

        HTTPException : Code 404, Could not find row
        """
        if kwargs.get("id", row_id) != row_id:
            raise HTTPException(status_code=400, detail="ID mismatch between URL and body")
        try:
            async with session.begin_nested():
                row = await session.get(cls, row_id)
                if row is None:
                    raise HTTPException(status_code=404, detail=f"{cls} {row_id} not found")
                for var, value in kwargs.items():
                    setattr(row, var, value)
            await session.refresh(row)
            return row
        except IntegrityError as e:
            raise HTTPException(422, detail=str(e)) from e

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
        # This is a stupid workaround to fool mypy
        cls_copy = cls
        if TYPE_CHECKING:
            assert issubclass(cls_copy, RowMixin)
        create_kwargs = await cls_copy.get_create_kwargs(session, **kwargs)
        row = cls(**create_kwargs)
        async with session.begin_nested():
            session.add(row)
        await session.refresh(row)
        return row

    @classmethod
    async def get_create_kwargs(
        cls: type[T],
        session: async_scoped_session,  # pylint: disable=unused-argument
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
        HTTPException : Code 422, IntegrityError
        """
        try:
            async with session.begin_nested():
                for var, value in kwargs.items():
                    setattr(self, var, value)
            await session.refresh(self)
            return self
        except IntegrityError as e:
            raise HTTPException(422, detail=str(e)) from e