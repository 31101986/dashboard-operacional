# (1) Escolhemos uma imagem base do Python 3.11
FROM python:3.11-slim

# (2) Instalações básicas para poder instalar o ODBC driver
#    e também dependências do msodbcsql17 (ou 18).
#    No Debian/Ubuntu, precisamos do curl, gnupg, etc.

RUN apt-get update && apt-get install -y curl gnupg apt-transport-https ca-certificates

# (3) Adiciona o repositório oficial da Microsoft (para o msodbcsql)
#    A Microsoft oferece pacotes para Debian/Ubuntu. Ajuste se quiser msodbcsql18
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
RUN curl https://packages.microsoft.com/config/debian/11/prod.list \
    > /etc/apt/sources.list.d/mssql-release.list

# (4) Instala o msodbcsql17 ou msodbcsql18
#    e as dependências do unixodbc
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y \
    msodbcsql17 \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# (5) Cria diretório do app no contêiner
WORKDIR /app

# (6) Copia os arquivos do seu projeto para /app
#    Ajuste se o seu repositório tiver subpastas. 
#    Se seu requirements.txt está na raiz, você copia tudo.
COPY . /app

# (7) Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# (8) Define a porta que o Gunicorn vai escutar
EXPOSE 8000

# (9) Variável de ambiente (opcional) - faz o Flask/Dash rodar no "production"
ENV PYTHONUNBUFFERED=1

# (10) Comando final: inicia o Gunicorn apontando para seu app:server
#     Ajuste se o seu app principal tiver outro nome ou se o server se chama
#     app.server, etc. 
CMD gunicorn app:server -b 0.0.0.0:8000
