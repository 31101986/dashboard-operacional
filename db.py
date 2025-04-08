from contextlib import contextmanager
from functools import lru_cache
import logging
import os
import time
import urllib.parse
from typing import Any, Iterator, Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool

from config import db_config, logger as root_logger

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = root_logger.getChild(__name__)

# ---------------------------------------------------------------------------
# Engine creation & management
# ---------------------------------------------------------------------------

_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))

def _build_connection_string() -> str:
    connection_string = (
        "DRIVER={{{driver}}};SERVER={server};DATABASE={database};UID={user};PWD={password};"
        "Encrypt=no;TrustServerCertificate=yes;"
    ).format(**db_config)
    params = urllib.parse.quote_plus(connection_string)
    return f"mssql+pyodbc:///?odbc_connect={params}"

@lru_cache(maxsize=1)
def create_db_engine() -> Engine:  # type: ignore[name‑defined]
    """Return a singleton SQLAlchemy Engine with sane defaults."""
    engine = create_engine(
        _build_connection_string(),
        poolclass=QueuePool,
        pool_size=_POOL_SIZE,
        max_overflow=_MAX_OVERFLOW,
        pool_pre_ping=True,  # Recycle dead connections automatically
        fast_executemany=True,  # Speed‑up bulk operations (pyodbc‑specific)
        connect_args={"timeout": 30},  # seconds
    )
    logger.info("SQLAlchemy engine created (pool_size=%s, max_overflow=%s)", _POOL_SIZE, _MAX_OVERFLOW)
    return engine

# Expose a module‑level engine for backwards compatibility
engine: Engine = create_db_engine()

# ---------------------------------------------------------------------------
# Helper: cached query results (simple in‑memory TTL cache)
# ---------------------------------------------------------------------------

_cache: dict[str, tuple[float, pd.DataFrame]] = {}

def _maybe_from_cache(sql: str, cache_seconds: int | None) -> Optional[pd.DataFrame]:
    if not cache_seconds:
        return None
    current_time = time.time()
    entry = _cache.get(sql)
    if entry and (current_time - entry[0] < cache_seconds):
        logger.debug("Cache hit for SQL (age %.1fs)", current_time - entry[0])
        return entry[1]
    return None

def _store_cache(sql: str, df: pd.DataFrame, cache_seconds: int | None) -> None:
    if cache_seconds:
        _cache[sql] = (time.time(), df)

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def query_to_df(
    query: str,
    params: Optional[dict[str, Any] | list[Any] | tuple[Any, ...]] = None,
    *,
    chunksize: Optional[int] = None,
    cache_seconds: Optional[int] = None,
) -> pd.DataFrame | Iterator[pd.DataFrame]:
    """Execute *query* and return a *pandas* DataFrame (or an iterator).

    Parameters
    ----------
    query
        SQL statement (use parameter placeholders understood by SQLAlchemy).
    params
        Parameters passed to the database driver (dict / list / tuple).
    chunksize
        When provided, returns an *iterator* yielding chunks of that size. Use
        this for very large result sets to keep memory usage bounded.
    cache_seconds
        If given, the result DataFrame is cached in‑memory for that many
        seconds. Useful for dashboards where users repeat the same expensive
        query within a short time window.
    """
    if chunksize is None:  # Only full‑result queries are cached
        cached = _maybe_from_cache(query, cache_seconds)
        if cached is not None:
            return cached.copy()  # Defensive copy so caller can mutate

    try:
        if chunksize:
            logger.debug("Running query in chunksize=%s", chunksize)
            return pd.read_sql(text(query), engine, params=params, chunksize=chunksize)
        df = pd.read_sql(text(query), engine, params=params)
        _store_cache(query, df, cache_seconds)
        return df
    except Exception as exc:
        logger.exception("Error executing query: %s", query)
        raise

def close_engine() -> None:
    """Dispose the global engine and clear the cache."""
    global engine
    try:
        if engine:
            engine.dispose()
            logger.info("Engine disposed")
            _cache.clear()
            # Invalidate cached singleton so future calls recreate a fresh engine
            create_db_engine.cache_clear()  # type: ignore[attr‑defined]
            engine = None  # type: ignore[assignment]
    except Exception:
        logger.exception("Error disposing engine")
        raise

# Make sure connections are released when the interpreter terminates
import atexit  # noqa: E402
atexit.register(close_engine)

# Public API expected by legacy code
__all__ = [
    "create_db_engine",
    "engine",
    "query_to_df",
    "close_engine",
]
