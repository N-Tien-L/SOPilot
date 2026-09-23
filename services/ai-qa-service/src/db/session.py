from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
import asyncpg
from typing import AsyncGenerator
import structlog

from ..config.settings import settings

logger = structlog.get_logger()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        await session.execute(text(f"SET search_path TO {settings.database_schema}, knowledge, metadata, core, public"))
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_pool() -> asyncpg.Pool:
    if not hasattr(get_db_pool, "_pool"):
        get_db_pool._pool = await asyncpg.create_pool(
            settings.database_url.replace("+asyncpg", ""),
            min_size=5,
            max_size=20
        )
    return get_db_pool._pool


async def close_db_pool() -> None:
    """Close the asyncpg connection pool. Call during application shutdown."""
    if hasattr(get_db_pool, "_pool") and get_db_pool._pool:
        await get_db_pool._pool.close()
        del get_db_pool._pool
        logger.info("asyncpg_pool_closed")


async def get_connection() -> asyncpg.Connection:
    pool = await get_db_pool()
    return await pool.acquire()


async def release_connection(conn: asyncpg.Connection):
    pool = await get_db_pool()
    await pool.release(conn)