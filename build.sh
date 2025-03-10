#!/usr/bin/env bash
set -e  # faz o script parar caso algum comando dê erro

echo "=== Iniciando script de instalação do ODBC Driver e das dependências ==="

# 1) Atualiza o repositório
sudo apt-get update

# 2) Instala pacotes necessários para baixar e instalar o driver
sudo apt-get install -y curl apt-transport-https gnupg2

# 3) Adiciona a chave GPG e o repositório da Microsoft (para Ubuntu 20.04 ou 22.04)
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/20.04/prod.list \
    | sudo tee /etc/apt/sources.list.d/mssql-release.list

# Se estiver usando Ubuntu 22.04 no container do Render, troque a linha acima por:
# curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list \
#     | sudo tee /etc/apt/sources.list.d/mssql-release.list

# 4) Atualiza e instala o driver ODBC 18 + unixodbc-dev
sudo apt-get update
ACCEPT_EULA=Y sudo apt-get install -y msodbcsql18 unixodbc-dev

echo "=== ODBC Driver 18 instalado com sucesso ==="

# 5) Agora instalamos as dependências Python
pip install -r requirements.txt

echo "=== Script build.sh finalizado com sucesso ==="
