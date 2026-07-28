#!/usr/bin/env bash
# Start the DJ Playlist Converter local web app.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ ! -d venv ]]; then
  echo "No venv found. Run setup first:"
  echo "  python3 -m venv venv && source venv/bin/activate"
  echo "  pip install -r requirements.txt && pip install -e ."
  echo "  cd frontend && npm install && npm run build"
  exit 1
fi

# shellcheck disable=SC1091
source venv/bin/activate

if [[ ! -d frontend/dist ]]; then
  echo "Building UI (frontend/dist missing)…"
  (cd frontend && npm install && npm run build)
fi

PORT="${PORT:-8000}"
URL="http://127.0.0.1:${PORT}"

echo "Starting DJ Playlist Converter at ${URL}"
echo "Press Ctrl+C to stop."

export PYTHONPATH=src
exec uvicorn dj_converter.main:app --reload --host 127.0.0.1 --port "$PORT"
