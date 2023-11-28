from sqlalchemy import Enum

from ..common.enums import (
    ErrorAction,
    ErrorFlavor,
    ErrorSource,
    LevelEnum,
    NodeTypeEnum,
    ProductStatusEnum,
    ScriptMethod,
    StatusEnum,
    TableEnum,
    TaskStatusEnum,
    WmsMethod,
)
from .base import Base

SqlTableEnum = Enum(TableEnum, metadata=Base.metadata)
SqlNodeTypeEnum = Enum(NodeTypeEnum, metadata=Base.metadata)
SqlLevelEnum = Enum(LevelEnum, metadata=Base.metadata)
SqlStatusEnum = Enum(StatusEnum, metadata=Base.metadata)
SqlTaskStatusEnum = Enum(TaskStatusEnum, metadata=Base.metadata)
SqlProductStatusEnum = Enum(ProductStatusEnum, metadata=Base.metadata)
SqlErrorSource = Enum(ErrorSource, metadata=Base.metadata)
SqlErrorFlavor = Enum(ErrorFlavor, metadata=Base.metadata)
SqlErrorAction = Enum(ErrorAction, metadata=Base.metadata)
SqlScriptMethod = Enum(ScriptMethod, metadata=Base.metadata)
SqlWmsMethod = Enum(WmsMethod, metadata=Base.metadata)
