from db import get_engine, query_to_df

# Testa a criação da engine
engine = get_engine()
print("Engine criada com sucesso!")

# Exemplo de consulta (altere "sua_tabela" para o nome de uma tabela existente)
try:
    df = query_to_df("SELECT TOP 10 * FROM sua_tabela")
    print(df.head())
except Exception as e:
    print(f"Erro na consulta: {e}")
