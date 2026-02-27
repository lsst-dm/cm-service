from sqlalchemy import Enum as saEnum
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from lsst.cmservice.cm_models.enums import StatusEnum

from ..settings import settings


class Base(DeclarativeBase):
    """Base class for DB tables"""

    metadata = MetaData(schema=settings.table_schema)
    type_annotation_map = {
        StatusEnum: saEnum(StatusEnum, length=20, native_enum=False, create_constraint=False),
    }
