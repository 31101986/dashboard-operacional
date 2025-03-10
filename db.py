from sqlalchemy import create_engine
import pandas as pd
from config import db_config
import urllib.parse

def get_engine():
    # Monta a string de conexão usando os parâmetros do db_config
    connection_string = (
        f"DRIVER={{{db_config['driver']}}};"
        f"SERVER={db_config['server']};"
        f"DATABASE={db_config['database']};"
        f"UID={db_config['user']};"
        f"PWD={db_config['password']};"
        "Encrypt=no;"
        "TrustServerCertificate=yes;"
    )
    # Codifica a string de conexão para ser utilizada na URL do SQLAlchemy
    params = urllib.parse.quote_plus(connection_string)
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")
    return engine

def query_to_df(query, params=None):
    # Abre uma conexão, executa a consulta e retorna os resultados como DataFrame
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params)
    engine.dispose()
    return df
