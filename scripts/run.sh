#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

ensure_dependencies() {
  if ! "$PYTHON_BIN" -c "import openpyxl" >/dev/null 2>&1; then
    "$PYTHON_BIN" -m pip install -r "$ROOT_DIR/requirements.txt"
  fi
}

if [[ "${1:-}" == "--sync-deps" ]]; then
  shift
  "$PYTHON_BIN" -m pip install -r "$ROOT_DIR/requirements.txt"
else
  ensure_dependencies
fi

"$PYTHON_BIN" "$ROOT_DIR/lotto.py" "$@"
