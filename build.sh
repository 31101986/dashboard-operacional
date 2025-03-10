#!/usr/bin/env bash
set -eux

# Atualiza a lista de pacotes e instala ferramentas necessárias
apt-get update && apt-get install -y curl gnupg apt-transport-https

# Importa a chave pública da Microsoft
curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -

# Adiciona o repositório da Microsoft (para Debian 11; se necessário, adapte para a sua distribuição)
curl https://packages.microsoft.com/config/debian/11/prod.list | tee /etc/apt/sources.list.d/mssql-release.list

# Atualiza novamente e instala o driver ODBC 17 para SQL Server e os arquivos de desenvolvimento do unixODBC
apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc-dev

# (Opcional) Instale outras dependências do sistema, se necessário

# Atualiza o pip e instala as dependências do seu projeto
pip install --upgrade pip
pip install -r requirements.txt
