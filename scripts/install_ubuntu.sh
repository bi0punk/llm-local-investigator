#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-$PWD}"

sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip jq curl lm-sensors smartmontools nvme-cli

cd "$PROJECT_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

mkdir -p outputs snapshots db
cp -n .env.example .env || true

echo "Instalación base lista."
echo "Recuerda levantar llama-server y ajustar .env"
