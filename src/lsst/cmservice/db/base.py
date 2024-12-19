from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from ..config import config


class Base(DeclarativeBase):
    """Base class for DB tables"""

    metadata = MetaData(schema=config.db.table_schema)
