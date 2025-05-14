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

from config import PROJECTS_CONFIG, db_config, logger as root_logger

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = root_logger.getChild(__name__)

# ---------------------------------------------------------------------------
# Engine creation & management
# ---------------------------------------------------------------------------

_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
_engines: dict[str, Engine] = {}
_server_running = True  # Flag to prevent cleanup during server operation

def _build_connection_string(projeto: str = 'projeto1') -> str:
    """Build an ODBC connection string for the specified project."""
    if projeto not in PROJECTS_CONFIG:
        logger.error("Project %s not configured in PROJECTS_CONFIG", projeto)
        raise KeyError(f"Project {projeto} not configured")
    
    config = PROJECTS_CONFIG[projeto]
    connection_string = (
        "DRIVER={{{driver}}};SERVER={server};DATABASE={database};UID={user};PWD={password};"
        "Encrypt=no;TrustServerCertificate=yes;"
    ).format(**config)
    params = urllib.parse.quote_plus(connection_string)
    return f"mssql+pyodbc:///?odbc_connect={params}"

@lru_cache(maxsize=5)
def create_db_engine(projeto: str = 'projeto1') -> Engine:
    """Return a SQLAlchemy Engine for the specified project with sane defaults."""
    engine = create_engine(
        _build_connection_string(projeto),
        poolclass=QueuePool,
        pool_size=_POOL_SIZE,
        max_overflow=_MAX_OVERFLOW,
        pool_pre_ping=True,  # Keep for now, test without if needed
        fast_executemany=True,
        connect_args={"timeout": 30},
    )
    logger.info("SQLAlchemy engine created for project %s (pool_size=%s, max_overflow=%s)", 
                projeto, _POOL_SIZE, _MAX_OVERFLOW)
    return engine

def get_engine(projeto: str = 'projeto1') -> Engine:
    """Return the SQLAlchemy Engine for the specified project, creating it if necessary."""
    if projeto not in _engines:
        _engines[projeto] = create_db_engine(projeto)
    return _engines[projeto]

# Expose a module-level engine for backwards compatibility
engine: Engine = get_engine('projeto1')

# ---------------------------------------------------------------------------
# Helper: cached query results (simple in-memory TTL cache)
# ---------------------------------------------------------------------------

_cache: dict[str, tuple[float, pd.DataFrame]] = {}
_CACHE_LIMIT = 100

def _maybe_from_cache(sql: str, cache_seconds: int | None) -> Optional[pd.DataFrame]:
    if not cache_seconds:
        return None
    current_time = time.time()
    entry = _cache.get(sql)
    if entry and (current_time - entry[0] < cache_seconds):
        logger.debug("Cache hit for SQL (age %.1fs)", current_time - entry[0])
        return entry[1].copy()
    return None

def _store_cache(sql: str, df: pd.DataFrame, cache_seconds: int | None) -> None:
    if cache_seconds:
        if len(_cache) >= _CACHE_LIMIT:
            _cache.pop(next(iter(_cache)))
        _cache[sql] = (time.time(), df.copy())

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def query_to_df(
    query: str,
    params: Optional[dict[str, Any] | list[Any] | tuple[Any, ...]] = None,
    *,
    chunksize: Optional[int] = None,
    cache_seconds: Optional[int] = None,
    projeto: str = 'projeto1'
) -> pd.DataFrame | Iterator[pd.DataFrame]:
    """Execute *query* for the specified project and return a *pandas* DataFrame (or an iterator)."""
    current_time = time.time()
    if chunksize is None:
        cached = _maybe_from_cache(query, cache_seconds)
        if cached is not None:
            return cached

    try:
        engine = get_engine(projeto)
        if chunksize:
            logger.debug("Running query in chunksize=%s for project %s", chunksize, projeto)
            return pd.read_sql(text(query), engine, params=params, chunksize=chunksize)
        df = pd.read_sql(text(query), engine, params=params)
        _store_cache(query, df, cache_seconds)
        logger.debug("Query executed successfully for project %s: %s", projeto, query)
        return df
    except Exception as exc:
        logger.error("Error executing query for project %s: %s", projeto, str(exc))
        raise

def close_engine() -> None:
    """Dispose all project engines and clear the cache."""
    global _server_running
    if _server_running:
        logger.warning("Attempted to close engines while server is running. Skipping.")
        return
    try:
        for projeto, eng in _engines.items():
            eng.dispose()
            logger.info("Engine disposed for project %s", projeto)
        _engines.clear()
        _cache.clear()
        create_db_engine.cache_clear()
    except Exception:
        logger.exception("Error disposing engines")
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