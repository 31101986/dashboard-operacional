# Usando a imagem base do Python 3.11 slim
FROM python:3.11-slim

# (1) Instala pacotes básicos necessários para compilar extensões em C++ 
# (como o pyodbc) e adiciona pacotes para habilitar repositórios da Microsoft
RUN apt-get update && apt-get install -y \
    curl gnupg apt-transport-https ca-certificates g++ \
 && rm -rf /var/lib/apt/lists/*

# (2) Adiciona a chave GPG da Microsoft e o repositório para o ODBC
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
 && curl https://packages.microsoft.com/config/debian/11/prod.list \
    > /etc/apt/sources.list.d/mssql-release.list

# (3) Instala o driver msodbcsql18 e as bibliotecas do unixodbc
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y \
    msodbcsql18 \
    unixodbc-dev \
 && rm -rf /var/lib/apt/lists/*

# (4) Define a pasta de trabalho dentro do container
WORKDIR /app

# (5) Copia todo o conteúdo do projeto para dentro do container
COPY . /app

# (6) Instala as dependências Python, incluindo pyodbc
RUN pip install --no-cache-dir -r requirements.txt

# (7) Expõe a porta que seu servidor Flask/Gunicorn irá escutar
EXPOSE 8000

# (8) Comando que inicia a aplicação
CMD ["gunicorn", "app:server", "-b", "0.0.0.0:8000"]
