from collections.abc import Callable, Sequence
from typing import TypeAlias

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models
from ..common.enums import StatusEnum


def get_rows_no_parent_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.RowMixin,
    class_string: str = "",
) -> Callable:
    assert issubclass(db_class, db.RowMixin)

    @router.get(
        "/list",
        response_model=list[response_model_class],
        summary=f"List {class_string}s",
    )
    async def get_rows(
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
        "/list",
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
        summary=f"Retrieve a {class_string} by name",
    )
    async def get_row(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        return await db_class.get_row(session, row_id)

    return get_row


def get_row_by_fullname_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.RowMixin,
    class_string: str = "",
) -> Callable:
    @router.get(
        "/get",
        response_model=response_model_class,
        summary=f"Retrieve a {class_string} by name",
    )
    async def get_row_by_fullname(
        fullname: str,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        return await db_class.get_row_by_fullname(session, fullname)

    return get_row_by_fullname


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


def get_node_spec_block_function(
    router: APIRouter,
    db_class: TypeAlias = db.NodeMixin,
    class_string: str = "",
) -> Callable:
    @router.get(
        "/spec_block",
        response_model=models.SpecBlock,
        summary=f"Get the SpecBlock associated to a {class_string}",
    )
    async def get_node_spec_block(
        fullname: str,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> models.SpecBlock:
        the_node = await db_class.get_row_by_fullname(session, fullname)
        return await the_node.get_spec_block(session)

    return get_node_spec_block


def get_node_specification_function(
    router: APIRouter,
    db_class: TypeAlias = db.NodeMixin,
    class_string: str = "",
) -> Callable:
    @router.get(
        "/specification",
        response_model=models.Specification,
        summary=f"Get the Specification associated to a {class_string}",
    )
    async def get_node_specification(
        fullname: str,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> models.Specification:
        the_node = await db_class.get_row_by_fullname(session, fullname)
        return await the_node.get_specification(session)

    return get_node_specification


def get_node_parent_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.NodeMixin,
    class_string: str = "",
) -> Callable:
    @router.get(
        "/parent",
        response_model=response_model_class,
        summary=f"Get the Parent associated to a {class_string}",
    )
    async def get_node_parent(
        fullname: str,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row_by_fullname(session, fullname)
        return await the_node.get_parent(session)

    return get_node_parent


def get_node_resolved_collections_function(
    router: APIRouter,
    db_class: TypeAlias = db.NodeMixin,
    class_string: str = "",
) -> Callable:
    @router.get(
        "/resolved_collections",
        response_model=dict[str, str],
        summary=f"Get the resolved collections associated to a {class_string}",
    )
    async def get_node_resolved_collections(
        fullname: str,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> dict[str, str]:
        the_node = await db_class.get_row_by_fullname(session, fullname)
        return await the_node.resolve_collections(session)

    return get_node_resolved_collections


def get_node_collections_function(
    router: APIRouter,
    db_class: TypeAlias = db.NodeMixin,
    class_string: str = "",
) -> Callable:
    @router.get(
        "/collections",
        response_model=dict[str, str],
        summary=f"Get the collections associated to a {class_string}",
    )
    async def get_node_collections(
        fullname: str,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> dict[str, str]:
        the_node = await db_class.get_row_by_fullname(session, fullname)
        return await the_node.get_collections(session)

    return get_node_collections


def get_node_child_config_function(
    router: APIRouter,
    db_class: TypeAlias = db.NodeMixin,
    class_string: str = "",
) -> Callable:
    @router.get(
        "/child_config",
        response_model=dict[str, str],
        summary=f"Get the child_config associated to a {class_string}",
    )
    async def get_node_child_config(
        fullname: str,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> dict[str, str]:
        the_node = await db_class.get_row_by_fullname(session, fullname)
        return await the_node.get_child_config(session)

    return get_node_child_config


def get_node_data_dict_function(
    router: APIRouter,
    db_class: TypeAlias = db.NodeMixin,
    class_string: str = "",
) -> Callable:
    @router.get(
        "/data_dict",
        response_model=dict[str, str],
        summary=f"Get the data_dict associated to a {class_string}",
    )
    async def get_node_data_dict(
        fullname: str,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> dict[str, str]:
        the_node = await db_class.get_row_by_fullname(session, fullname)
        return await the_node.get_data_dict(session)

    return get_node_data_dict


def get_node_spec_aliases_function(
    router: APIRouter,
    db_class: TypeAlias = db.NodeMixin,
    class_string: str = "",
) -> Callable:
    @router.get(
        "/spec_aliases",
        response_model=dict[str, str],
        summary=f"Get the spec_aliases associated to a {class_string}",
    )
    async def get_node_spec_aliases(
        fullname: str,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> dict[str, str]:
        the_node = await db_class.get_row_by_fullname(session, fullname)
        return await the_node.get_spec_aliases(session)

    return get_node_spec_aliases


def update_node_collections_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.NodeMixin,
    class_string: str = "",
) -> Callable:
    @router.post(
        "/collections",
        status_code=201,
        response_model=response_model_class,
        summary=f"Update the collections associated to a {class_string}",
    )
    async def update_node_collections(
        query: models.UpdateNodeQuery,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row_by_fullname(session, query.fullname)
        return await the_node.update_collections(session, **query.update_dict)

    return update_node_collections


def update_node_child_config_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.NodeMixin,
    class_string: str = "",
) -> Callable:
    @router.post(
        "/child_config",
        response_model=response_model_class,
        summary=f"Update the child_config associated to a {class_string}",
    )
    async def update_node_child_config(
        query: models.UpdateNodeQuery,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row_by_fullname(session, query.fullname)
        return await the_node.update_child_config(session, **query.update_dict)

    return update_node_child_config


def update_node_data_dict_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.NodeMixin,
    class_string: str = "",
) -> Callable:
    @router.get(
        "/data_dict",
        response_model=response_model_class,
        summary=f"Update the data_dict associated to a {class_string}",
    )
    async def update_node_data_dict(
        query: models.UpdateNodeQuery,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row_by_fullname(session, query.fullname)
        return await the_node.update_data_dict(session, **query.update_dict)

    return update_node_data_dict


def update_node_spec_aliases_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.NodeMixin,
    class_string: str = "",
) -> Callable:
    @router.get(
        "/spec_aliases",
        response_model=response_model_class,
        summary=f"Update the spec_aliases associated to a {class_string}",
    )
    async def update_node_spec_aliases(
        query: models.UpdateNodeQuery,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row_by_fullname(session, query.fullname)
        return await the_node.update_spec_aliases(session, **query.update_dict)

    return update_node_spec_aliases


def get_node_check_prerequisites_function(
    router: APIRouter,
    db_class: TypeAlias = db.NodeMixin,
    class_string: str = "",
) -> Callable:
    @router.get(
        "/check_prerequisites",
        response_model=bool,
        summary=f"Check the prerequisites associated to a {class_string}",
    )
    async def node_check_prerequisites(
        fullname: str,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> bool:
        the_node = await db_class.get_row_by_fullname(session, fullname)
        return await the_node.check_prerequisites(session)

    return node_check_prerequisites


def get_node_reject_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.NodeMixin,
    class_string: str = "",
) -> Callable:
    @router.post(
        "/reject",
        status_code=201,
        response_model=response_model_class,
        summary=f"Mark a {class_string} as rejected",
    )
    async def node_reject(
        fullname: str,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row_by_fullname(session, fullname)
        return await the_node.reject(session)

    return node_reject


def get_node_accept_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.NodeMixin,
    class_string: str = "",
) -> Callable:
    @router.post(
        "/accept",
        status_code=201,
        response_model=response_model_class,
        summary=f"Mark a {class_string} as accepted",
    )
    async def node_accept(
        fullname: str,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row_by_fullname(session, fullname)
        return await the_node.accept(session)

    return node_accept


def get_node_reset_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.NodeMixin,
    class_string: str = "",
) -> Callable:
    @router.post(
        "/reset",
        status_code=201,
        response_model=response_model_class,
        summary=f"Mark a {class_string} as reseted",
    )
    async def node_reset(
        fullname: str,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row_by_fullname(session, fullname)
        return await the_node.reset(session)

    return node_reset


def get_node_process_function(
    router: APIRouter,
    response_model_class: TypeAlias = tuple[bool, StatusEnum],
    db_class: TypeAlias = db.NodeMixin,
    class_string: str = "",
) -> Callable:
    @router.post(
        "/process",
        status_code=201,
        response_model=response_model_class,
        summary=f"Mark a {class_string} as processed",
    )
    async def node_process(
        fullname: str,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row_by_fullname(session, fullname)
        return await the_node.process(session)

    return node_process


def get_node_run_check_function(
    router: APIRouter,
    response_model_class: TypeAlias = tuple[bool, StatusEnum],
    db_class: TypeAlias = db.NodeMixin,
    class_string: str = "",
) -> Callable:
    @router.post(
        "/run_check",
        status_code=201,
        response_model=response_model_class,
        summary=f"Mark a {class_string} as run_checked",
    )
    async def node_run_check(
        fullname: str,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row_by_fullname(session, fullname)
        return await the_node.run_check(session)

    return node_run_check
