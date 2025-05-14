from __future__ import annotations

"""config.py

Utility helpers to centralise application-wide configuration such as database
credentials, production targets and default time-zone.

The module keeps the public surface identical to the original version so that
imports such as::

    from config import db_config, DB_CONFIG, META_MINERIO, TIMEZONE

continue to work unchanged when the calling code simply replaces the old
module by this one.

Adiciona suporte para múltiplos projetos, carregando credenciais de bancos de dados
para projeto1 (FAS), projeto2 (FAC), projeto3 (FES), projeto4 (FET), e projeto5 (FPB).
Credenciais do projeto1 são obrigatórias; outros projetos são opcionais, com avisos
logados se ausentes.
"""

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from zoneinfo import ZoneInfo  # Python ≥3.9

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _setup_logger() -> logging.Logger:
    """Return a module-level logger with a sensible default format.

    The log level can be tuned through the *LOG_LEVEL* environment variable so
    that the application can switch between noisy *DEBUG* during development
    and quieter *INFO* or *WARNING* in production without code changes.
    """
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger = logging.getLogger(__name__)
    if not logger.handlers:  # Avoid duplicate setup
        logger.setLevel(level)
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s - %(name)s: %(message)s")
        )
        logger.addHandler(handler)
        logger.propagate = False
    return logger


logger = _setup_logger()

# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------

load_dotenv()  # Loads .env into process env, if present.

_DB_ENV_KEYS: Dict[str, str] = {
    "server": "DB_SERVER",
    "database": "DB_NAME",
    "user": "DB_USER",
    "password": "DB_PASSWORD",
    "driver": "DB_DRIVER",
}

# Pré-carregar variáveis de ambiente uma vez
_env_vars = {f"{env_key}{suffix}": os.getenv(f"{env_key}{suffix}") for env_key in _DB_ENV_KEYS.values() for suffix in ['', '_PROJETO2', '_PROJETO3', '_PROJETO4', '_PROJETO5']}

@lru_cache(maxsize=1)
def load_db_config() -> Dict[str, Dict[str, str]]:
    """Return database connection parameters for all projects sourced from environment variables.

    The result is cached so repeated calls do not re-read the environment.
    Returns a dictionary where each key is a project ID (projeto1, projeto2, etc.)
    and each value is a dictionary with connection parameters (server, database, user, password, driver).
    Credentials for projeto1 are mandatory; other projects are optional, with warnings logged if missing.
    """
    projects = ['projeto1', 'projeto2', 'projeto3', 'projeto4', 'projeto5']
    projects_config = {}
    
    for projeto in projects:
        suffix = '' if projeto == 'projeto1' else f"_PROJETO{projeto.replace('projeto', '')}"
        config = {key: _env_vars.get(f"{_DB_ENV_KEYS[key]}{suffix}") for key in _DB_ENV_KEYS}
        
        logger.debug(f"Variables for {projeto}:")
        for key, value in config.items():
            logger.debug(f"  {key}: {'****' if key == 'password' else value}")
        
        missing = [key for key, value in config.items() if not value]
        if missing:
            msg = (
                f"Missing environment variables for {projeto}: "
                f"{', '.join(_DB_ENV_KEYS[m] for m in missing)}"
            )
            if projeto == 'projeto1':
                logger.error(msg)
                raise ValueError(msg)
            else:
                logger.warning(msg)
                continue
        
        projects_config[projeto] = config
    
    if not projects_config:
        msg = "No valid project configurations found in environment variables"
        logger.error(msg)
        raise ValueError(msg)
    
    logger.debug(
        "Database configuration successfully loaded for projects: %s",
        {k: {kk: vv if kk != 'password' else '****' for kk, vv in v.items()} for k, v in projects_config.items()}
    )
    return projects_config


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
# Project labels
# ---------------------------------------------------------------------------

PROJECT_LABELS: Dict[str, str] = {
    'projeto1': 'FAS',
    'projeto2': 'FAC',
    'projeto3': 'FES',
    'projeto4': 'FET',
    'projeto5': 'FPB'
}


# ---------------------------------------------------------------------------
# Public constants exposed at import-time for convenience
# ---------------------------------------------------------------------------

PROJECTS_CONFIG: Dict[str, Dict[str, str]] = load_db_config()
DB_CONFIG: Dict[str, str] = PROJECTS_CONFIG['projeto1']
# Backward-compatibility alias so legacy code importing *db_config* keeps working
db_config: Dict[str, str] = DB_CONFIG

_METAS: Dict[str, Any] = load_metas()

META_MINERIO: int = int(_METAS["meta_minerio"])
META_ESTERIL: int = int(_METAS["meta_esteril"])

# Time-zone can be overridden via APP_TZ env variable (useful for tests)
TIMEZONE: ZoneInfo = ZoneInfo(os.getenv("APP_TZ", "America/Sao_Paulo"))

# What this module exports when someone does *from config import *
__all__ = [
    "logger",
    "DB_CONFIG",
    "db_config",
    "PROJECTS_CONFIG",
    "PROJECT_LABELS",
    "META_MINERIO",
    "META_ESTERIL",
    "TIMEZONE",
    "load_db_config",
    "load_metas",
]