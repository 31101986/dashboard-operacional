import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

def setup_logger():
    """
    Configura e retorna um logger para a aplicação.
    """
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    # Evita adicionar múltiplos handlers se já estiver configurado
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        logger_formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
        console_handler.setFormatter(logger_formatter)
        logger.addHandler(console_handler)
    return logger

logger = setup_logger()

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

def load_db_config():
    """
    Carrega as configurações do banco de dados a partir das variáveis de ambiente.
    """
    env_keys = {
        "server": "DB_SERVER",
        "database": "DB_NAME",
        "user": "DB_USER",
        "password": "DB_PASSWORD",
        "driver": "DB_DRIVER",
    }
    db_config = { key: os.getenv(env_key) for key, env_key in env_keys.items() }
    
    if not all(db_config.values()):
        msg = (
            "Uma ou mais variáveis de ambiente não foram definidas corretamente. "
            "Verifique o arquivo .env e se os valores para 'DB_SERVER', 'DB_NAME', "
            "'DB_USER', 'DB_PASSWORD' e 'DB_DRIVER' estão presentes."
        )
        logger.error(msg)
        raise ValueError(msg)
    
    logger.info(f"Configurações de banco de dados carregadas com sucesso: {db_config}")
    return db_config

db_config = load_db_config()

def load_metas():
    """
    Carrega as metas do arquivo 'metas.json' localizado no mesmo diretório deste script.
    """
    current_dir = Path(__file__).parent
    metas_path = current_dir / "metas.json"
    
    try:
        with metas_path.open(mode="r", encoding="utf-8") as f:
            metas = json.load(f)
        logger.info(f"Métas carregadas de {metas_path}")
        return metas
    except FileNotFoundError:
        msg = f"Arquivo 'metas.json' não encontrado em {metas_path}."
        logger.error(msg)
        raise ValueError(msg)
    except json.JSONDecodeError as e:
        msg = f"Erro ao decodificar 'metas.json': {e}"
        logger.error(msg)
        raise ValueError(msg)
    except Exception as e:
        msg = f"Erro ao carregar o arquivo 'metas.json': {e}"
        logger.error(msg)
        raise ValueError(msg)

metas = load_metas()

# Definição das metas com valores padrão caso não estejam presentes no JSON
META_MINERIO = metas.get("meta_minerio", 1901)
META_ESTERIL = metas.get("meta_esteril", 21555)
