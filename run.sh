#!/usr/bin/env bash
# ZoneScore — single-entrypoint launcher (bare-metal, no Docker).
# Usage: ./run.sh [--offline] [--rebuild] [--port N]
set -euo pipefail

cd "$(dirname "$0")"

PORT=8000
for arg in "$@"; do
  case "$arg" in
    --offline) export URBIS_OFFLINE=1 ;;
    --rebuild) REBUILD=1 ;;
    --port) : ;; # value handled below
    *) [[ "${prev:-}" == "--port" ]] && PORT="$arg" ;;
  esac
  prev="$arg"
done

PY=python
command -v python3 >/dev/null 2>&1 && PY=python3

if [[ ! -d .venv ]]; then
  echo "[run.sh] Creating virtual environment (.venv)…"
  "$PY" -m venv .venv
fi

if [[ -f .venv/Scripts/python.exe ]]; then
  VENV_PY=.venv/Scripts/python.exe   # Windows (Git Bash)
else
  VENV_PY=.venv/bin/python           # Linux / macOS
fi

echo "[run.sh] Installing dependencies…"
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet -r backend/requirements.txt

if [[ "${REBUILD:-0}" == "1" ]]; then
  echo "[run.sh] Rebuilding data artifacts…"
  rm -f data/processed/zones_res*.parquet data/processed/zones_*.parquet data/processed/zonescore.duckdb data/processed/urbisqc.duckdb
fi

echo "[run.sh] Starting ZoneScore on http://127.0.0.1:${PORT} …"
cd backend
exec "../$VENV_PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
