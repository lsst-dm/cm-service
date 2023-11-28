from sqlalchemy import Enum

from ..common.enums import (
    ErrorActionEnum,
    ErrorFlavorEnum,
    ErrorSourceEnum,
    LevelEnum,
    NodeTypeEnum,
    ProductStatusEnum,
    ScriptMethodEnum,
    StatusEnum,
    TableEnum,
    TaskStatusEnum,
    WmsMethodEnum,
)
from .base import Base

SqlTableEnum = Enum(TableEnum, metadata=Base.metadata)
SqlNodeTypeEnum = Enum(NodeTypeEnum, metadata=Base.metadata)
SqlLevelEnum = Enum(LevelEnum, metadata=Base.metadata)
SqlStatusEnum = Enum(StatusEnum, metadata=Base.metadata)
SqlTaskStatusEnum = Enum(TaskStatusEnum, metadata=Base.metadata)
SqlProductStatusEnum = Enum(ProductStatusEnum, metadata=Base.metadata)
SqlErrorSourceEnum = Enum(ErrorSourceEnum, metadata=Base.metadata)
SqlErrorFlavorEnum = Enum(ErrorFlavorEnum, metadata=Base.metadata)
SqlErrorActionEnum = Enum(ErrorActionEnum, metadata=Base.metadata)
SqlScriptMethodEnum = Enum(ScriptMethodEnum, metadata=Base.metadata)
SqlWmsMethodEnum = Enum(WmsMethodEnum, metadata=Base.metadata)
