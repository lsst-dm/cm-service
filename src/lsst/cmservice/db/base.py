from sqlalchemy import Enum as saEnum
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from ..common.enums import (
    ErrorActionEnum,
    ErrorFlavorEnum,
    ErrorSourceEnum,
    LevelEnum,
    ScriptMethodEnum,
    StatusEnum,
)
from ..config import config


class Base(DeclarativeBase):
    """Base class for DB tables"""

    metadata = MetaData(schema=config.db.table_schema)
    type_annotation_map = {
        ErrorActionEnum: saEnum(ErrorActionEnum, length=20, native_enum=False, create_constraint=False),
        ErrorFlavorEnum: saEnum(ErrorFlavorEnum, length=20, native_enum=False, create_constraint=False),
        ErrorSourceEnum: saEnum(ErrorSourceEnum, length=20, native_enum=False, create_constraint=False),
        LevelEnum: saEnum(LevelEnum, length=20, native_enum=False, create_constraint=False),
        ScriptMethodEnum: saEnum(ScriptMethodEnum, length=20, native_enum=False, create_constraint=False),
        StatusEnum: saEnum(StatusEnum, length=20, native_enum=False, create_constraint=False),
    }
