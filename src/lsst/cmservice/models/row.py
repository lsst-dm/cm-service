from pydantic import BaseModel

from ..common.enums import TableEnum


class RowQuery(BaseModel):
    table_enum: TableEnum
    row_id: int


class RowData(BaseModel):
    data: dict

    class Config:
        orm_mode = False
