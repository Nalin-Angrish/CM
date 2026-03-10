"""Async database connection pool for MCP resource queries."""

import os
import asyncpg

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://cloudmgr:changeme_in_production@database:5432/cloudmgr",
)

_pool: asyncpg.Pool | None = None


def _normalize_url(url: str) -> str:
    """Strip SQLAlchemy async driver prefix if present."""
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            _normalize_url(DATABASE_URL), min_size=2, max_size=10
        )
    return _pool


async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
