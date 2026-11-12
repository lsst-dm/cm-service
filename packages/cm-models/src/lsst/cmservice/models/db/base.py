from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlmodel import MetaData, SQLModel

from .settings import settings

metadata: MetaData = MetaData(schema=settings.table_schema)
"""SQLModel metadata for table models"""


class BaseSQLModel(AsyncAttrs, SQLModel):
    """Shared base SQL model for all SQLModel-based tables."""

    __table_args__ = {"schema": settings.table_schema}
    metadata = metadata
