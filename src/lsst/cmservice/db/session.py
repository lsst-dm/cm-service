"""Module to create and handle async database sessions"""

from collections.abc import AsyncGenerator

from sqlalchemy import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool, Pool
from sqlmodel.ext.asyncio.session import AsyncSession

from ..common.logging import LOGGER
from ..config import config

logger = LOGGER.bind(module=__name__)


class DatabaseSessionDependency:
    """A database session manager class designed to manage an async sqlalchemy
    engine and produce sessions.

    A module-level instance of this class is created, and when called, a new
    async session is yielded.
    """

    engine: AsyncEngine | None
    sessionmaker: async_sessionmaker[AsyncSession] | None
    url: URL
    pool_class: type[Pool] = AsyncAdaptedQueuePool

    def __init__(self) -> None:
        self.engine = None
        self.sessionmaker = None

    async def initialize(
        self,
        *,
        use_async: bool = True,
    ) -> None:
        """Initialize the session dependency.

        Parameters
        ----------
        use_async
            If true (default), the database drivername will be forced to an
            async form.
        """
        await self.aclose()
        if isinstance(config.db.url, str):
            self.url = make_url(config.db.url)
        if use_async and self.url.drivername == "postgresql":
            self.url = self.url.set(drivername="postgresql+asyncpg")
        if config.db.password is not None:
            self.url = self.url.set(password=config.db.password.get_secret_value())
        pool_kwargs = (
            config.db.model_dump(include=config.db.pool_fields)
            if self.pool_class is AsyncAdaptedQueuePool
            else {}
        )
        self.engine = create_async_engine(
            url=self.url,
            echo=config.db.echo,
            poolclass=self.pool_class,
            **pool_kwargs,
        )
        self.sessionmaker = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def __call__(self) -> AsyncGenerator[AsyncSession]:
        """Yields a database session, rolls it back on error and closes it on
        completion.

        Yields
        -------
        sqlmodel.ext.asyncio.AsyncSession
            The newly-created session.
        """
        if not self.sessionmaker:
            raise RuntimeError("Async sessionmaker is not initialized")

        async with self.sessionmaker() as session:
            try:
                yield session
            except Exception:
                logger.exception()
                await session.rollback()
                raise
            finally:
                await session.close()

    async def aclose(self) -> None:
        """Shut down the database engine."""
        if self.engine:
            self.sessionmaker = None
            await self.engine.dispose()
            self.engine = None


db_session_dependency = DatabaseSessionDependency()
"""A module-level instance of the session manager"""


# FIXME not sure why this pattern
async def get_async_session() -> AsyncSession:
    """Get a new session from the current database session factory."""
    return await anext(db_session_dependency())
