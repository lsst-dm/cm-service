"""Module to create and handle async database sessions"""

from collections.abc import AsyncGenerator

# from pydantic import SecretStr  #noqa: ERA001
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from ..config import config


class DatabaseSessionDependency:
    """A database session manager class designed to manage an async sqlalchemy
    engine and produce sessions.

    A module-level instance of this class is created, and when called, a new
    async session is yielded.
    """

    def __init__(self) -> None:
        self.engine: AsyncEngine | None = None
        self.sessionmaker: async_sessionmaker[AsyncSession] | None = None

    async def initialize(
        self,
        *,
        isolation_level: str | None = None,
        use_async: bool = True,
        echo: bool = False,
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
        if isinstance(config.db.url, str):
            url = make_url(config.db.url)
        if use_async and url.drivername == "postgresql":
            url = url.set(drivername="postgresql+asyncpg")
        # FIXME use SecretStr for password
        # if isinstance(config.db.password, SecretStr):
        #     password = config.db.password.get_secret_value()  #noqa: ERA001
        if config.db.password is not None:
            url = url.set(password=config.db.password)
        if self.engine:
            await self.engine.dispose()
        self.engine = create_async_engine(
            url=url,
            echo=config.db.echo,
            # TODO add pool-level configs
        )
        self.sessionmaker = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def __call__(self) -> AsyncGenerator[AsyncSession]:
        """Yields a database session.

        Yields
        -------
        sqlmodel.ext.asyncio.AsyncSession
            The newly-created session.
        """
        if not self.sessionmaker:
            raise RuntimeError("Async sessionmaker is not initialized")

        async with self.sessionmaker() as session:
            yield session

    async def aclose(self) -> None:
        """Shut down the database engine."""
        if self.engine:
            self.sessionmaker = None
            await self.engine.dispose()
            self._engine = None


db_session_dependency = DatabaseSessionDependency()
"""A module-level instance of the session manager"""


# FIXME not sure why this pattern
async def get_async_session() -> AsyncSession:
    return await anext(db_session_dependency())
