"""
Database Manager

Manages SQLAlchemy async engine and session factory for PostgreSQL.
"""

import logging

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages the async database engine and session factory.

    Singleton per application — created once at startup.
    """

    def __init__(self, database_url: str, pool_size: int = 5, echo: bool = False) -> None:
        # Ensure we use the async driver
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        self._engine: AsyncEngine = create_async_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=10,
            echo=echo,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info("Database manager initialized")

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    def get_session(self) -> AsyncSession:
        """Create a new async session."""
        return self._session_factory()

    async def close(self) -> None:
        """Close the engine and all connections."""
        await self._engine.dispose()
        logger.info("Database connections closed")
