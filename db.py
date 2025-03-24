import logging
import pandas as pd
import urllib.parse
from sqlalchemy import create_engine
from config import db_config

# -----------------------------------------------------------------------------
# Configuração básica de logs (opcional, mas recomendado)
# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Se preferir, configure um StreamHandler para ver logs no console
console_handler = logging.StreamHandler()
console_format = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
console_handler.setFormatter(console_format)
logger.addHandler(console_handler)

# -----------------------------------------------------------------------------
# Criação do engine e reuso ao longo da aplicação
# -----------------------------------------------------------------------------
def create_db_engine():
    """
    Cria e retorna um engine SQLAlchemy com base nas configurações fornecidas.
    Em caso de falha, registra erro nos logs e relança a exceção.
    """
    try:
        connection_string = (
            f"DRIVER={{{db_config['driver']}}};"
            f"SERVER={db_config['server']};"
            f"DATABASE={db_config['database']};"
            f"UID={db_config['user']};"
            f"PWD={db_config['password']};"
            "Encrypt=no;"
            "TrustServerCertificate=yes;"
        )
        params = urllib.parse.quote_plus(connection_string)
        engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")
        logger.info("Engine criado com sucesso.")
        return engine
    except Exception as e:
        logger.error(f"Erro ao criar engine: {e}")
        raise

# -----------------------------------------------------------------------------
# Inicializa o engine de forma global
# -----------------------------------------------------------------------------
engine = create_db_engine()

# -----------------------------------------------------------------------------
# Função de consulta com suporte a DataFrame e “chunking”
# -----------------------------------------------------------------------------
def query_to_df(query, params=None, chunksize=None):
    """
    Executa uma query SQL e retorna um DataFrame.
    
    Parâmetros:
      - query (str): instrução SQL a ser executada.
      - params (dict|list|tuple, opcional): parâmetros para substituir na query.
      - chunksize (int, opcional): se fornecido, retorna um iterador de DataFrames 
                                   com esse tamanho de chunk; caso contrário,
                                   retorna apenas um DataFrame único.

    Exemplo de uso:
      - df = query_to_df("SELECT * FROM Tabela")
      - df_iter = query_to_df("SELECT * FROM Tabela", chunksize=5000)
    """
    try:
        if chunksize:
            # Retorna um iterador de chunks (DataFrames) para lidar com muitos dados
            df_iter = pd.read_sql(query, engine, params=params, chunksize=chunksize)
            return df_iter
        else:
            # Retorna um único DataFrame
            df = pd.read_sql(query, engine, params=params)
            return df
    except Exception as e:
        logger.error(f"Erro ao executar query:\n{query}\nParâmetros: {params}\n{e}")
        raise

# -----------------------------------------------------------------------------
# Função para finalizar/descartar conexões, se necessário
# (Normalmente utilizada ao encerrar a aplicação)
# -----------------------------------------------------------------------------
def close_engine():
    try:
        if engine:
            engine.dispose()
            logger.info("Engine descartado com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao descartar engine: {e}")
        raise
