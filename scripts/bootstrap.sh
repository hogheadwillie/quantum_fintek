#!/usr/bin/env bash
set -euo pipefail

echo "QuantumFintek bootstrap"
echo "Creating Python virtual environment..."
python -m venv .venv
source .venv/bin/activate

echo "Installing quant-core and ai-intel in editable mode..."
pip install -e packages/quant-core
pip install -e packages/ai-intel

echo "Installing API requirements..."
pip install -r apps/api/requirements.txt

echo "Done. Activate with: source .venv/bin/activate"
