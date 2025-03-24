import os
import json
import logging
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# Configuração básica de logs (opcional)
# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Caso queira ver logs no console, inclua um StreamHandler
console_handler = logging.StreamHandler()
logger_formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
console_handler.setFormatter(logger_formatter)
logger.addHandler(console_handler)

# -----------------------------------------------------------------------------
# Carrega variáveis de ambiente do arquivo .env
# -----------------------------------------------------------------------------
load_dotenv()

# -----------------------------------------------------------------------------
# Montagem do dicionário de configuração do banco de dados
# -----------------------------------------------------------------------------
db_config = {
    "server": os.getenv("DB_SERVER"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "driver": os.getenv("DB_DRIVER"),
}

# -----------------------------------------------------------------------------
# Validação das variáveis de ambiente
# -----------------------------------------------------------------------------
if not all(db_config.values()):
    msg = (
        "Uma ou mais variáveis de ambiente não foram definidas corretamente. "
        "Verifique o arquivo .env e se os valores para 'DB_SERVER', 'DB_NAME', "
        "'DB_USER', 'DB_PASSWORD' e 'DB_DRIVER' estão lá."
    )
    logger.error(msg)
    raise ValueError(msg)

logger.info(f"Configurações de banco de dados carregadas com sucesso: {db_config}")

# -----------------------------------------------------------------------------
# Carrega as metas do arquivo metas.json
# -----------------------------------------------------------------------------
current_dir = os.path.dirname(__file__)
metas_path = os.path.join(current_dir, "metas.json")

try:
    with open(metas_path, mode="r", encoding="utf-8") as f:
        metas = json.load(f)
    logger.info(f"Métas carregadas de {metas_path}")
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

# -----------------------------------------------------------------------------
# Definição das metas como constantes ou variáveis
# -----------------------------------------------------------------------------
META_MINERIO = metas.get("meta_minerio", 1901)
META_ESTERIL = metas.get("meta_esteril", 21555)
