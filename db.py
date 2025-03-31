import logging
import pandas as pd
import urllib.parse
from sqlalchemy import create_engine
from config import db_config


def setup_logger():
    """
    Configura e retorna um logger para a aplicação.
    Garante que não sejam adicionados múltiplos handlers em execuções repetidas.
    """
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_format = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)
    return logger


logger = setup_logger()


def create_db_engine():
    """
    Cria e retorna um engine SQLAlchemy com base nas configurações fornecidas.
    Em caso de falha, registra o erro e relança a exceção.
    """
    try:
        # Monta a string de conexão
        connection_string = (
            f"DRIVER={{{db_config['driver']}}};"
            f"SERVER={db_config['server']};"
            f"DATABASE={db_config['database']};"
            f"UID={db_config['user']};"
            f"PWD={db_config['password']};"
            "Encrypt=no;"
            "TrustServerCertificate=yes;"
        )
        # Codifica a string de conexão para uso em URL
        params = urllib.parse.quote_plus(connection_string)

        # Cria o engine usando PyODBC + SQLAlchemy
        engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")
        logger.info("Engine criado com sucesso.")
        return engine
    except Exception as e:
        logger.error(f"Erro ao criar engine: {e}")
        raise


# Inicializa o engine de forma global para reuso na aplicação
engine = create_db_engine()


def query_to_df(query, params=None, chunksize=None):
    """
    Executa uma query SQL e retorna um DataFrame ou um iterador de DataFrames.

    Parâmetros:
      - query (str): instrução SQL a ser executada.
      - params (dict|list|tuple, opcional): parâmetros para a query.
      - chunksize (int, opcional): se fornecido, retorna um iterador de DataFrames com o tamanho do chunk;
                                   caso contrário, retorna um único DataFrame.

    Exemplo:
      - df = query_to_df("SELECT * FROM Tabela")
      - df_iter = query_to_df("SELECT * FROM Tabela", chunksize=5000)
    """
    try:
        if chunksize:
            # Utiliza chunksize para lidar com grandes volumes de dados sem sobrecarregar a memória
            return pd.read_sql(query, engine, params=params, chunksize=chunksize)
        else:
            return pd.read_sql(query, engine, params=params)
    except Exception as e:
        logger.error(f"Erro ao executar query:\n{query}\nParâmetros: {params}\n{e}")
        raise


def close_engine():
    """
    Finaliza (descarta) o engine, liberando conexões.
    Normalmente chamado ao encerrar a aplicação.
    """
    try:
        if engine:
            engine.dispose()
            logger.info("Engine descartado com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao descartar engine: {e}")
        raise
