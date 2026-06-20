#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY_DIR="$ROOT_DIR/python-backend"
VENV_DIR="$ROOT_DIR/.venv"

echo "Creating virtualenv in $VENV_DIR"
python3 -m venv "$VENV_DIR"

echo "Activating virtualenv and installing dependencies"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
pip install -r "$PY_DIR/requirements-cpu.txt"

echo "Installing MineForgeAI backend as editable package"
pip install -e "$PY_DIR"

cat <<'EOF'
Installation complete.
Activate the environment with:
  source .venv/bin/activate
Run the CLI with:
  mineforge  # or use `node bin/mineforge.js` for the node launcher
EOF
