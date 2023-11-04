from fastapi import APIRouter, Depends
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models
from ..handlers import interface

router = APIRouter(
    prefix="/update",
    tags=["Updates"],
)


@router.post(
    "/status",
    status_code=201,
    response_model=models.Element,
    summary="Update status field associated to a node",
)
async def update_status(
    query: models.UpdateStatusQuery,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.NodeMixin:
    result = await interface.update_status(
        session,
        query.fullname,
        query.status,
    )
    return result


@router.post(
    "/collections",
    status_code=201,
    response_model=models.Element,
    summary="Update collections field associated to a node",
)
async def update_collections(
    query: models.UpdateNodeQuery,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.NodeMixin:
    result = await interface.update_collections(
        session,
        query.fullname,
        **query.update_dict,
    )
    return result


@router.post(
    "/child_config",
    status_code=201,
    response_model=models.Element,
    summary="Update child_config field associated to a node",
)
async def update_child_config(
    query: models.UpdateNodeQuery,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.NodeMixin:
    result = await interface.update_child_config(
        session,
        query.fullname,
        **query.update_dict,
    )
    return result


@router.post(
    "/data_dict",
    status_code=201,
    response_model=models.Element,
    summary="Update data_dict field associated to a node",
)
async def update_data_dict(
    query: models.UpdateNodeQuery,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.NodeMixin:
    result = await interface.update_data_dict(
        session,
        query.fullname,
        **query.update_dict,
    )
    return result


@router.post(
    "/spec_aliases",
    status_code=201,
    response_model=models.Element,
    summary="Update spec_aliases field associated to a node",
)
async def update_spec_aliases(
    query: models.UpdateNodeQuery,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.NodeMixin:
    result = await interface.update_spec_aliases(
        session,
        query.fullname,
        **query.update_dict,
    )
    return result
