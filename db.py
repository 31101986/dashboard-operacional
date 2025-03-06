from sqlalchemy import create_engine
import pandas as pd
from config import db_config
import urllib.parse

def get_engine():
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
    return engine

def query_to_df(query, params=None):
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params)
    engine.dispose()
    return df
