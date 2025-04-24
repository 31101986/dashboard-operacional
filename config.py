from __future__ import annotations

"""config_optimized.py

Utility helpers to centralise application‑wide configuration such as database
credentials, production targets and default time‑zone.

The module keeps the public surface identical to the original version so that
imports such as::

    from config import db_config, DB_CONFIG, META_MINERIO, TIMEZONE

continue to work unchanged when the calling code simply replaces the old
module by this one.
"""

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from zoneinfo import ZoneInfo  # Python ≥3.9

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _setup_logger() -> logging.Logger:
    """Return a module‑level logger with a sensible default format.

    The log level can be tuned through the *LOG_LEVEL* environment variable so
    that the application can switch between noisy *DEBUG* during development
    and quieter *INFO* or *WARNING* in production without code changes.
    """

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger = logging.getLogger(__name__)
    logger.setLevel(level)

    # Prevent duplication when the module is re‑imported (e.g. by hot reload)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s ‑ %(name)s: %(message)s")
        )
        logger.addHandler(handler)
        # Avoid propagating to the root logger which could have its own handler
        logger.propagate = False
    return logger


logger = _setup_logger()

# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------

load_dotenv()  # Loads .env into process env, if present.

_DB_ENV_KEYS: dict[str, str] = {
    "server": "DB_SERVER",
    "database": "DB_NAME",
    "user": "DB_USER",
    "password": "DB_PASSWORD",
    "driver": "DB_DRIVER",
}


@lru_cache(maxsize=1)
def load_db_config() -> dict[str, str]:
    """Return database connection parameters sourced from environment variables.

    The result is cached so repeated calls do not re‑read the environment.
    """

    db_config = {key: os.getenv(env_key) for key, env_key in _DB_ENV_KEYS.items()}
    missing = [key for key, value in db_config.items() if not value]
    if missing:
        msg = (
            "Missing required environment variables for database connection: "
            f"{', '.join(_DB_ENV_KEYS[m] for m in missing)}"
        )
        logger.error(msg)
        raise ValueError(msg)

    logger.debug("Database configuration successfully loaded")
    return db_config


# ---------------------------------------------------------------------------
# Production targets (metas)
# ---------------------------------------------------------------------------

_DEFAULT_METAS: dict[str, Any] = {"meta_minerio": 5500, "meta_esteril": 23000}


@lru_cache(maxsize=1)
def load_metas(file_path: str | Path | None = None) -> dict[str, Any]:
    """Load production targets from a JSON file and merge with defaults.

    Parameters
    ----------
    file_path
        Optional path to the JSON file. When omitted the function looks for a
        *metas.json* file located alongside this module.
    """

    path = Path(file_path) if file_path else Path(__file__).with_name("metas.json")
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        logger.debug("Loaded metas from %s", path)
        return {**_DEFAULT_METAS, **data}
    except FileNotFoundError as exc:
        msg = f"File '{path}' not found."
        logger.exception(msg)
        raise ValueError(msg) from exc
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON in '{path}': {exc}"
        logger.exception(msg)
        raise ValueError(msg) from exc


# ---------------------------------------------------------------------------
# Public constants exposed at import‑time for convenience
# ---------------------------------------------------------------------------

DB_CONFIG: dict[str, str] = load_db_config()
# Backward‑compatibility alias so legacy code importing *db_config* keeps working
# without modifications.  Lowercase name mirrors the original module.
db_config: dict[str, str] = DB_CONFIG

_METAS: dict[str, Any] = load_metas()

META_MINERIO: int = int(_METAS["meta_minerio"])
META_ESTERIL: int = int(_METAS["meta_esteril"])

# Time‑zone can be overridden via APP_TZ env variable (useful for tests)
TIMEZONE: ZoneInfo = ZoneInfo(os.getenv("APP_TZ", "America/Sao_Paulo"))

# What this module exports when someone does *from config import *
__all__ = [
    "logger",
    "DB_CONFIG",
    "db_config",
    "META_MINERIO",
    "META_ESTERIL",
    "TIMEZONE",
    "load_db_config",
    "load_metas",
]
