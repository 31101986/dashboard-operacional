import os
import json
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env
load_dotenv()

# Configuração do Banco de Dados
db_config = {
    "server": os.getenv("DB_SERVER"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "driver": os.getenv("DB_DRIVER"),
}

if not all(db_config.values()):
    raise ValueError("Uma ou mais variáveis de ambiente não foram definidas corretamente. Verifique o arquivo .env.")

# Carrega as Metas a partir do arquivo metas.json
metas_path = os.path.join(os.path.dirname(__file__), "metas.json")
try:
    with open(metas_path, "r", encoding="utf-8") as f:
        metas = json.load(f)
except Exception as e:
    raise ValueError(f"Erro ao carregar o arquivo 'metas.json': {e}")

META_MINERIO = metas.get("meta_minerio", 1901)
META_ESTERIL = metas.get("meta_esteril", 21555)
