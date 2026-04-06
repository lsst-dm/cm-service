from pydantic import BaseModel, ConfigDict

from ..common.enums import TableEnum


class RowQuery(BaseModel):
    """Pydantic model for selecting a row from a table"""

    table_enum: TableEnum
    row_id: int


class RowData(BaseModel):
    """Pydantic model for getting data field from a row in a table"""

    model_config = ConfigDict(from_attributes=True)

    data: dict
