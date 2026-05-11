# FIX: trava no Debian 12 porque a Microsoft não tem driver para Debian 13 ainda
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ACCEPT_EULA=Y

# (1) Dependências de sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg2 apt-transport-https ca-certificates g++ unixodbc-dev \
 && rm -rf /var/lib/apt/lists/*

# (2) Chave Microsoft - método novo, sem apt-key
RUN mkdir -p /usr/share/keyrings \
 && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
 && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
    > /etc/apt/sources.list.d/mssql-release.list

# (3) Instala o driver ODBC 18
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
    msodbcsql18 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# (4) Instala Python primeiro (cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# (5) Copia o projeto
COPY . .

EXPOSE 10000

CMD ["gunicorn", "app:server", "-b", "0.0.0.0:10000", "--workers", "2"]
