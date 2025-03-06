import pyodbc

driver = "ODBC Driver 17 for SQL Server"  # Verifique se esse é o nome correto
server = "www.minetrack.com.br,8112"
database = "DW_SDP_MT_FAS"
user = "SRV_FAS_CONSULTA"
password = "Sodep123!@#"

connection_str = (
    f"DRIVER={{{driver}}};"
    f"SERVER={server};"
    f"DATABASE={database};"
    f"UID={user};"
    f"PWD={password};"
)

try:
    conn = pyodbc.connect(connection_str)
    print("Conexão realizada com sucesso!")
    conn.close()
except Exception as e:
    print("Erro ao conectar:")
    print(e)
