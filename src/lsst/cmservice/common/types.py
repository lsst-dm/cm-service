from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionSA
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlmodel.ext.asyncio.session import AsyncSession

type AnyAsyncSession = AsyncSession | AsyncSessionSA | async_scoped_session
"""A type union of async database sessions the application may use"""
