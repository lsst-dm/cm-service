"""Module to create and handle async database sessions"""

from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session


async def get_async_scoped_session() -> async_scoped_session:
    """Provides an async session from the safir session maker."""
    return await anext(db_session_dependency())
