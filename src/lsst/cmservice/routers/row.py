from fastapi import APIRouter, Depends, HTTPException
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import models
from ..common.enums import TableEnum
from ..common.errors import CMBadEnumError, CMBadExecutionMethodError, CMMissingFullnameError
from ..db.node import NodeMixin
from ..handlers.interface import get_row_by_table_and_id

router = APIRouter(
    prefix="/rows",
    tags=["Rows"],
)


@router.get(
    "/{table_name}/{row_id}",
    response_model=models.RowData,
    summary="Retrieve data from a particular row of the Db",
)
async def get_row_data(
    table_name: str,
    row_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> dict:
    """Invoke the interface.get_row_by_table_and_id function"""
    table_enum = TableEnum[table_name]
    try:
        async with session.begin():
            result = await get_row_by_table_and_id(session, row_id, table_enum)
    except (CMBadEnumError, CMMissingFullnameError, CMMissingFullnameError) as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg
    if not isinstance(result, NodeMixin):
        raise CMBadExecutionMethodError(f"Result is a {type(result)}, not a subclass of NodeMixin")
    data_dict = await result.data_dict(session)
    return {"data": data_dict}


@router.post(
    "",
    status_code=201,
    response_model=models.RowData,
    summary="Ask for a given row",
)
async def post_row(
    row_query: models.RowQuery,
    session: async_scoped_session = Depends(db_session_dependency),
) -> dict:
    """Invoke the interface.get_row_by_table_and_id function"""
    try:
        async with session.begin():
            row = await get_row_by_table_and_id(
                session,
                row_query.row_id,
                row_query.table_enum,
            )
    except (CMBadEnumError, CMMissingFullnameError, CMMissingFullnameError) as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg
    if not isinstance(row, NodeMixin):
        raise CMBadExecutionMethodError(f"Row is a {type(row)} not a subclass of NodeMixin")
    return await row.data_dict(session)
