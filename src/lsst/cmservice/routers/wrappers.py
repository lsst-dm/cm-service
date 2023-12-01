from collections.abc import Callable, Sequence
from typing import TypeAlias

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db


def get_rows_no_parent_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.RowMixin,
    class_string: str = "",
) -> Callable:
    assert issubclass(db_class, db.RowMixin)

    @router.get(
        "",
        response_model=list[response_model_class],
        summary=f"List {class_string}s",
    )
    async def get_rows(
        parent_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> Sequence[response_model_class]:
        return await db_class.get_rows(
            session,
            skip=skip,
            limit=limit,
        )

    return get_rows


def get_rows_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.RowMixin,
    class_string: str = "",
) -> Callable:
    @router.get(
        "",
        response_model=list[response_model_class],
        summary=f"List {class_string}s",
    )
    async def get_rows(
        parent_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> Sequence[response_model_class]:
        return await db_class.get_rows(
            session,
            parent_id=parent_id,
            skip=skip,
            limit=limit,
            parent_class=db.Production,
        )

    return get_rows


def get_row_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.RowMixin,
    class_string: str = "",
) -> Callable:
    @router.get(
        "/{row_id}",
        response_model=response_model_class,
        summary=f"Retrieve a {class_string}",
    )
    async def get_row(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        return await db_class.get_row(session, row_id)

    return get_row


def post_row_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    create_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.RowMixin,
    class_string: str = "",
) -> Callable:
    @router.post(
        "",
        status_code=201,
        response_model=response_model_class,
        summary=f"Create a {class_string}",
    )
    async def post_row(
        row_create: create_model_class,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> db_class:
        result = await db_class.create_row(session, **row_create.dict())
        await session.commit()
        return result

    return post_row


def delete_row_function(
    router: APIRouter,
    db_class: TypeAlias = db.RowMixin,
    class_string: str = "",
) -> Callable:
    @router.delete(
        "/{row_id}",
        status_code=204,
        summary=f"Delete a {class_string}",
    )
    async def delete_row(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> None:
        await db_class.delete_row(session, row_id)

    return delete_row


def put_row_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.RowMixin,
    class_string: str = "",
) -> Callable:
    @router.put(
        "/{row_id}",
        response_model=response_model_class,
        summary=f"Update a {class_string}",
    )
    async def update_row(
        row_id: int,
        row_update: response_model_class,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> db_class:
        return await db_class.update_row(session, row_id, **row_update.dict())

    return update_row
