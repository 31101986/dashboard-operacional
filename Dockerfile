# Usando a imagem base do Python 3.11 slim
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ACCEPT_EULA=Y

# (1) Instala pacotes básicos necessários para compilar extensões em C++
# e para adicionar o repositório da Microsoft
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg2 apt-transport-https ca-certificates g++ unixodbc-dev \
 && rm -rf /var/lib/apt/lists/*

# (2) Adiciona a chave GPG da Microsoft SEM usar apt-key (corrigido)
RUN mkdir -p /usr/share/keyrings \
 && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg \
 && . /etc/os-release \
 && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/${VERSION_ID}/prod ${VERSION_CODENAME} main" \
    > /etc/apt/sources.list.d/mssql-release.list

# (3) Instala o driver msodbcsql18 e as bibliotecas do unixodbc
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
    msodbcsql18 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# (4) Define a pasta de trabalho dentro do container
WORKDIR /app

# (5) Copia requirements primeiro (melhora cache do Docker)
COPY requirements.txt .

# (6) Instala as dependências Python, incluindo pyodbc
RUN pip install --no-cache-dir -r requirements.txt

# (7) Copia o resto do projeto
COPY . /app

# (8) Expõe a porta que o Render usa
EXPOSE 10000

# (9) Comando que inicia a aplicação
CMD ["gunicorn", "app:server", "-b", "0.0.0.0:10000", "--workers", "2"]
