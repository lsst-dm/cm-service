"""Wrappers to create functions for the various routers

These wrappers create functions that invoke interface
functions that are defined in the db.row.RowMixin,
db.node.NodeMixin, and db.element.ElementMixin classes.

These make it easier to define router functions that
apply to all RowMixin, NodeMixin and ElementMixin classes."""

from collections.abc import Callable, Sequence
from typing import Any, TypeAlias

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
) -> Callable:
    """Return a function that gets all the rows from a table
    and attaches that function to a router.

    This version will provide a function that always returns
    all the rows

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    response_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the return value

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that return all the rows for the table in question
    """

    assert issubclass(db_class, db.RowMixin)

    @router.get(
        "/list",
        response_model=list[response_model_class],
        summary=f"List all the {db_class.class_string}",
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
) -> Callable:
    """Return a function that gets all the rows from a table
    and attaches that function to a router.

    This version will provide a function which can be filtered
    based on the id of the parent node.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    response_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the return value

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that return all the rows for the table in question
    """

    @router.get(
        "/list",
        response_model=list[response_model_class],
        summary=f"List all the {db_class.class_string}",
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
) -> Callable:
    """Return a function that gets a single row from a table (by ID)
    and attaches that function to a router.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    response_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the return value

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that returns a single row from a table by ID
    """

    @router.get(
        "/get/{row_id}",
        response_model=response_model_class,
        summary=f"Retrieve a {db_class.class_string} by name",
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
) -> Callable:
    """Return a function that gets a single row from a table (by name)
    and attaches that function to a router.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    response_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the return value

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that returns a single row from a table by name
    """

    @router.get(
        "/get",
        response_model=response_model_class,
        summary=f"Retrieve a {db_class.class_string} by name",
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
) -> Callable:
    """Return a function that creates a single row in a table
    and attaches that function to a router.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    response_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the return value

    create_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the inputs value

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that creates a single row in a table
    """

    @router.post(
        "/create",
        status_code=201,
        response_model=response_model_class,
        summary=f"Create a {db_class.class_string}",
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
) -> Callable:
    """Return a function that deletes a single row in a table
    and attaches that function to a router.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that delete a single row from a table by ID
    """

    @router.delete(
        "/delete/{row_id}",
        status_code=204,
        summary=f"Delete a {db_class.class_string}",
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
    update_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.RowMixin,
) -> Callable:
    """Return a function that updates a single row in a table
    and attaches that function to a router.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    response_model_class: TypeAlias = BaseModel
        Pydantic class used to serialize the return values

    update_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the input values

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that updates a single row from a table by ID
    """

    @router.put(
        "/update/{row_id}",
        response_model=response_model_class,
        summary=f"Update a {db_class.class_string}",
    )
    async def update_row(
        row_id: int,
        row_update: update_model_class,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> db_class:
        return await db_class.update_row(session, row_id, **row_update.dict())

    return update_row


def get_node_spec_block_function(
    router: APIRouter,
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function gets the SpecBlock associated to a Node.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that gets the SpecBlock associated to a Node
    """

    @router.get(
        "/get/{row_id}/spec_block",
        response_model=models.SpecBlock,
        summary=f"Get the SpecBlock associated to a {db_class.class_string}",
    )
    async def get_node_spec_block(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> models.SpecBlock:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.get_spec_block(session)

    return get_node_spec_block


def get_node_specification_function(
    router: APIRouter,
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function gets the Specification associated to a Node.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that gets the Specification associated to a Node
    """

    @router.get(
        "/get/{row_id}/specification",
        response_model=models.Specification,
        summary=f"Get the Specification associated to a {db_class.class_string}",
    )
    async def get_node_specification(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> models.Specification:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.get_specification(session)

    return get_node_specification


def get_node_parent_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function gets the parent Node associated to a Node.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    response_model_class: TypeAlias = BaseModel
        Pydantic class used to serialize the return value

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that gets the Specification associated to a Node
    """

    @router.get(
        "/get/{row_id}/parent",
        response_model=response_model_class,
        summary=f"Get the Parent associated to a {db_class.class_string}",
    )
    async def get_node_parent(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.get_parent(session)

    return get_node_parent


def get_node_resolved_collections_function(
    router: APIRouter,
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function gets resolved collection names associated to a Node.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that gets the resolved collection names associated to a Node
    """

    @router.get(
        "/get/{row_id}/resolved_collections",
        response_model=dict[str, str],
        summary=f"Get the resolved collections associated to a {db_class.class_string}",
    )
    async def get_node_resolved_collections(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> dict[str, str]:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.resolve_collections(session)

    return get_node_resolved_collections


def get_node_collections_function(
    router: APIRouter,
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function gets collection names associated to a Node.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that gets the collection names associated to a Node
    """

    @router.get(
        "/get/{row_id}/collections",
        response_model=dict[str, str],
        summary=f"Get the collections associated to a {db_class.class_string}",
    )
    async def get_node_collections(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> dict[str, str]:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.get_collections(session)

    return get_node_collections


def get_node_child_config_function(
    router: APIRouter,
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function gets child_conifg dict associated to a Node.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that gets the child_conifg dict associated to a Node
    """

    @router.get(
        "/get/{row_id}/child_config",
        response_model=dict[str, str],
        summary=f"Get the child_config associated to a {db_class.class_string}",
    )
    async def get_node_child_config(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> dict[str, str]:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.get_child_config(session)

    return get_node_child_config


def get_node_data_dict_function(
    router: APIRouter,
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function gets data_dict associated to a Node.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that gets the data_dict associated to a Node
    """

    @router.get(
        "/get/{row_id}/data_dict",
        response_model=dict[str, str],
        summary=f"Get the data_dict associated to a {db_class.class_string}",
    )
    async def get_node_data_dict(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> dict[str, str]:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.data_dict(session)

    return get_node_data_dict


def get_node_spec_aliases_function(
    router: APIRouter,
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function that gets the spec_aliases associated to a Node.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that gets the spec_aliases associated to a Node
    """

    @router.get(
        "/get/{row_id}/spec_aliases",
        response_model=dict[str, str],
        summary=f"Get the spec_aliases associated to a {db_class.class_string}",
    )
    async def get_node_spec_aliases(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> dict[str, str]:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.get_spec_aliases(session)

    return get_node_spec_aliases


def update_node_status_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function that updates the status of a Node.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    response_model_class: TypeAlias = BaseModel
        Pydantic class used to serialize the return value

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that updates the status of a Node.
    """

    @router.post(
        "/update/{row_id}/status",
        status_code=201,
        response_model=response_model_class,
        summary="Update status field associated to a node",
    )
    async def update_node_status(
        row_id: int,
        query: models.UpdateStatusQuery,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.update_values(session, status=query.status)

    return update_node_status


def update_node_collections_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function that updates the collections associated to a Node.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    response_model_class: TypeAlias = BaseModel
        Pydantic class used to serialize the return value

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that updates the collections associated to a Node.
    """

    @router.post(
        "/update/{row_id}/collections",
        status_code=201,
        response_model=response_model_class,
        summary=f"Update the collections associated to a {db_class.class_string}",
    )
    async def update_node_collections(
        row_id: int,
        query: models.UpdateNodeQuery,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.update_collections(session, **query.update_dict)

    return update_node_collections


def update_node_child_config_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function that updates the child_config associated to a Node.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    response_model_class: TypeAlias = BaseModel
        Pydantic class used to serialize the return value

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that updates the child_config associated to a Node.
    """

    @router.post(
        "/update/{row_id}/child_config",
        response_model=response_model_class,
        summary=f"Update the child_config associated to a {db_class.class_string}",
    )
    async def update_node_child_config(
        row_id: int,
        query: models.UpdateNodeQuery,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.update_child_config(session, **query.update_dict)

    return update_node_child_config


def update_node_data_dict_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function that updates the data_dict associated to a Node.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    response_model_class: TypeAlias = BaseModel
        Pydantic class used to serialize the return value

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that updates the data_dict associated to a Node.
    """

    @router.post(
        "/update/{row_id}/data_dict",
        response_model=response_model_class,
        summary=f"Update the data_dict associated to a {db_class.class_string}",
    )
    async def update_node_data_dict(
        row_id: int,
        query: models.UpdateNodeQuery,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.update_data_dict(session, **query.update_dict)

    return update_node_data_dict


def update_node_spec_aliases_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function that updates the spec_aliases associated to a Node.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    response_model_class: TypeAlias = BaseModel
        Pydantic class used to serialize the return value

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that updates the spec_aliases associated to a Node.
    """

    @router.post(
        "/update/{row_id}/spec_aliases",
        response_model=response_model_class,
        summary=f"Update the spec_aliases associated to a {db_class.class_string}",
    )
    async def update_node_spec_aliases(
        row_id: int,
        query: models.UpdateNodeQuery,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.update_spec_aliases(session, **query.update_dict)

    return update_node_spec_aliases


def get_node_check_prerequisites_function(
    router: APIRouter,
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function that checks the prerequisites of a Node.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that checks the prerequisites of a Node.
    """

    @router.get(
        "/get/{row_id}/check_prerequisites",
        response_model=bool,
        summary=f"Check the prerequisites associated to a {db_class.class_string}",
    )
    async def node_check_prerequisites(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> bool:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.check_prerequisites(session)

    return node_check_prerequisites


def get_node_reject_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function that marks a Node as rejected.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    response_model_class: TypeAlias = BaseModel
        Pydantic class used to serialize the return value

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that marks a Node as rejected.
    """

    @router.post(
        "/action/{row_id}/reject",
        status_code=201,
        response_model=response_model_class,
        summary=f"Mark a {db_class.class_string} as rejected",
    )
    async def node_reject(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.reject(session)

    return node_reject


def get_node_accept_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function that marks a Node as accepted.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    response_model_class: TypeAlias = BaseModel
        Pydantic class used to serialize the return value

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that marks a Node as accepted.
    """

    @router.post(
        "/action/{row_id}/accept",
        status_code=201,
        response_model=response_model_class,
        summary=f"Mark a {db_class.class_string} as accepted",
    )
    async def node_accept(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.accept(session)

    return node_accept


def get_node_reset_function(
    router: APIRouter,
    response_model_class: TypeAlias = BaseModel,
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function resets a Node status to waiting.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    response_model_class: TypeAlias = BaseModel
        Pydantic class used to serialize the return value

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that resets a Node status to waiting.
    """

    @router.post(
        "/action/{row_id}/reset",
        status_code=201,
        response_model=response_model_class,
        summary=f"Mark a {db_class.class_string} as reseted",
    )
    async def node_reset(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> response_model_class:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.reset(session)

    return node_reset


def get_node_process_function(
    router: APIRouter,
    response_model_class: TypeAlias = tuple[bool, StatusEnum],
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function that causes a Node to be processed.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    response_model_class: TypeAlias = BaseModel
        Pydantic class used to serialize the return value

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that causes a Node to be processed.
    """
    assert response_model_class

    @router.post(
        "/action/{row_id}/process",
        status_code=201,
        response_model=tuple[bool, StatusEnum],
        summary=f"Mark a {db_class.class_string} as processed",
    )
    async def node_process(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> tuple[bool, StatusEnum]:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.process(session)

    return node_process


def get_node_run_check_function(
    router: APIRouter,
    response_model_class: TypeAlias = tuple[bool, StatusEnum],
    db_class: TypeAlias = db.NodeMixin,
) -> Callable:
    """Return a function that checks the status of a Node.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    response_model_class: TypeAlias = BaseModel
        Pydantic class used to serialize the return value

    db_class: TypeAlias = db.RowMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that checks the status of a Node
    """
    assert response_model_class

    @router.post(
        "/action/{row_id}/run_check",
        status_code=201,
        response_model=tuple[bool, StatusEnum],
        summary=f"Mark a {db_class.class_string} as run_checked",
    )
    async def node_run_check(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
    ) -> tuple[bool, StatusEnum]:
        the_node = await db_class.get_row(session, row_id)
        return await the_node.run_check(session)

    return node_run_check


def get_element_get_scripts_function(
    router: APIRouter,
    db_class: TypeAlias = db.ElementMixin,
) -> Callable:
    """Return a function get the scripts associated to an Element.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    db_class: TypeAlias = db.ElementMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that get the scripts associated to an Element.
    """

    @router.get(
        "/get/{row_id}/scripts",
        status_code=201,
        response_model=Sequence[models.Script],
        summary=f"Get the scripts associated to a {db_class.class_string}",
    )
    async def element_get_scripts(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
        **kwargs: Any,
    ) -> tuple[bool, StatusEnum]:
        the_element = await db_class.get_row(session, row_id)
        return await the_element.get_scripts(session, **kwargs)

    return element_get_scripts


def get_element_get_all_scripts_function(
    router: APIRouter,
    db_class: TypeAlias = db.ElementMixin,
) -> Callable:
    """Return a function that gets all scripts associated to an Element.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    db_class: TypeAlias = db.ElementMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that gets all scripts associated to an Element.
    """

    @router.get(
        "/get/{row_id}/all_scripts",
        status_code=201,
        response_model=Sequence[models.Script],
        summary=f"Get the all scripts associated to a {db_class.class_string}",
    )
    async def element_get_all_scripts(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
        **kwargs: Any,
    ) -> tuple[bool, StatusEnum]:
        the_element = await db_class.get_row(session, row_id)
        return await the_element.get_all_scripts(session, **kwargs)

    return element_get_all_scripts


def get_element_get_jobs_function(
    router: APIRouter,
    db_class: TypeAlias = db.ElementMixin,
) -> Callable:
    """Return a function get the jobs associated to an Element.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    db_class: TypeAlias = db.ElementMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that jobs associated to an Element
    """

    @router.get(
        "/get/{row_id}/jobs",
        status_code=201,
        response_model=Sequence[models.Job],
        summary=f"Get the jobs associated to a {db_class.class_string}",
    )
    async def element_get_jobs(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
        **kwargs: Any,
    ) -> tuple[bool, StatusEnum]:
        the_element = await db_class.get_row(session, row_id)
        return await the_element.get_jobs(session, **kwargs)

    return element_get_jobs


def get_element_retry_script_function(
    router: APIRouter,
    db_class: TypeAlias = db.ElementMixin,
) -> Callable:
    """Return a function that will retry a script

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    db_class: TypeAlias = db.ElementMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that will retry a script
    """

    @router.post(
        "/get/{row_id}/retry_script",
        status_code=201,
        response_model=models.Script,
        summary=f"Retry a script associated to a {db_class.class_string}",
    )
    async def element_retry_script(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
        **kwargs: Any,
    ) -> tuple[bool, StatusEnum]:
        the_element = await db_class.get_row(session, row_id)
        return await the_element.retry_script(session, **kwargs)

    return element_retry_script


def get_element_estimate_sleep_time_function(
    router: APIRouter,
    db_class: TypeAlias = db.ElementMixin,
) -> Callable:
    """Return a function that will estimate how long to sleep before
    calling process again

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    db_class: TypeAlias = db.ElementMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that will estimate how long to sleep before
        calling process again
    """

    @router.post(
        "/get/{row_id}/estimate_sleep_time",
        status_code=201,
        response_model=int,
        summary=f"Retry a script associated to a {db_class.class_string}",
    )
    async def element_estimate_sleep_time(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
        **kwargs: Any,
    ) -> int:
        the_element = await db_class.get_row(session, row_id)
        return await the_element.estimate_sleep_time(session, **kwargs)

    return element_estimate_sleep_time


def get_element_wms_task_reports_function(
    router: APIRouter,
    db_class: TypeAlias = db.ElementMixin,
) -> Callable:
    """Return a function get the WmsTaskReports associated to an Element.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    db_class: TypeAlias = db.ElementMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that get the WmsTaskReports associated to an Element
    """

    @router.get(
        "/get/{row_id}/wms_task_reports",
        status_code=201,
        response_model=dict[str, models.WmsTaskReport],
        summary=f"Get the WmsTaskReports associated to a {db_class.class_string}",
    )
    async def element_get_wms_task_reports(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
        **kwargs: Any,
    ) -> dict[str, db.WmsTaskReport]:
        the_element = await db_class.get_row(session, row_id)
        return await the_element.get_wms_reports(session, **kwargs)

    return element_get_wms_task_reports


def get_element_tasks_function(
    router: APIRouter,
    db_class: TypeAlias = db.ElementMixin,
) -> Callable:
    """Return a function get the TaskSets associated to an Element.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    db_class: TypeAlias = db.ElementMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that get the TaskSets associated to an Element
    """

    @router.get(
        "/get/{row_id}/tasks",
        status_code=201,
        response_model=dict[str, models.TaskSet],
        summary=f"Get the TaskSets associated to a {db_class.class_string}",
    )
    async def element_get_tasks(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
        **kwargs: Any,
    ) -> dict[str, db.TaskSet]:
        the_element = await db_class.get_row(session, row_id)
        return await the_element.get_tasks(session, **kwargs)

    return element_get_tasks


def get_element_products_function(
    router: APIRouter,
    db_class: TypeAlias = db.ElementMixin,
) -> Callable:
    """Return a function get the ProductSets associated to an Element.

    Parameters
    ----------
    router: APIRouter
        Router to attach the function to

    db_class: TypeAlias = db.ElementMixin
        Underlying database class

    Returns
    -------
    the_function: Callable
        Function that get the ProductSets associated to an Element
    """

    @router.get(
        "/get/{row_id}/products",
        status_code=201,
        response_model=dict[str, models.ProductSet],
        summary=f"Get the ProductSets associated to a {db_class.class_string}",
    )
    async def element_get_products(
        row_id: int,
        session: async_scoped_session = Depends(db_session_dependency),
        **kwargs: Any,
    ) -> dict[str, db.ProductSet]:
        the_element = await db_class.get_row(session, row_id)
        return await the_element.get_products(session, **kwargs)

    return element_get_products
