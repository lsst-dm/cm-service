"""Module to create and handle async database sessions"""

from collections.abc import AsyncGenerator

from pydantic import SecretStr
from sqlalchemy import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlmodel import create_engine
from sqlmodel.ext.asyncio.session import AsyncSession


class DatabaseSessionDependency:
    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None

    async def initialize(
        self,
        url: str | URL,
        password: str | SecretStr | None,
        *,
        isolation_level: str | None = None,
        use_async: bool = True,
    ) -> None:
        """Initialize the session dependency.

        Parameters
        ----------
        url
            Database connection URL, not including the password.
        password
            Database connection password.
        isolation_level
            If specified, sets a non-default isolation level for the database
            engine.
        use_async
            If true (default), the database drivername will be forced to an
            async form.
        """
        if isinstance(url, str):
            url = make_url(url)
        if use_async and url.drivername == "postgresql":
            url = url.set(drivername="postgresql+asyncpg")
        if isinstance(password, SecretStr):
            password = password.get_secret_value()
        url = url.set(password=password)
        if self._engine:
            await self._engine.dispose()
        self._engine = AsyncEngine(create_engine(url))

    async def __call__(self) -> AsyncGenerator[AsyncSession]:
        """Yields a database session.

        Yields
        -------
        sqlmodel.ext.asyncio.AsyncSession
            The newly-created session.
        """
        async_session = async_sessionmaker(self._engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            yield session

    async def aclose(self) -> None:
        """Shut down the database engine."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None


db_session_dependency = DatabaseSessionDependency()
