from sqlalchemy import Enum as saEnum
from sqlalchemy import MetaData as saMetadata
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase
from sqlmodel import MetaData, SQLModel

from ..enums import StatusEnum
from .settings import settings

metadata: MetaData = MetaData(schema=settings.table_schema)
"""SQLModel metadata for table models"""


class Base(DeclarativeBase):
    """Base class for legacy sqlalchemy DB tables"""

    metadata = saMetadata(schema=settings.table_schema)
    type_annotation_map = {
        StatusEnum: saEnum(StatusEnum, length=20, native_enum=False, create_constraint=False),
    }


class BaseSQLModel(AsyncAttrs, SQLModel):
    """Shared base SQL model for all SQLModel-based tables."""

    __table_args__ = {"schema": settings.table_schema}
    metadata = metadata
