#!/usr/bin/env bash
set -e  # Faz o script "parar" se ocorrer erro em algum comando

echo "Instalando dependências do ODBC Driver..."
# Atualiza repositórios
sudo apt-get update

# Instala pacotes básicos para baixar e adicionar chaves
sudo apt-get install -y curl apt-transport-https gnupg2

# Adiciona o repositório da Microsoft para ODBC
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/20.04/prod.list \
    | sudo tee /etc/apt/sources.list.d/mssql-release.list

# Atualiza novamente e instala driver
sudo apt-get update
ACCEPT_EULA=Y sudo apt-get install -y msodbcsql18 unixodbc-dev

echo "Instalando as dependências Python..."
pip install -r requirements.txt

echo "Build concluído!"
