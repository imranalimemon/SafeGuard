#!/usr/bin/env bash
# Run from any directory; the process manager forwards signals and stops peers.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$ROOT"

for tool in node npm; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "[ERROR] $tool is missing. Follow README.md clean-machine setup." >&2
        exit 1
    fi
done
if [[ ! -f node_modules/.bin/concurrently ]]; then
    echo "[ERROR] Root dependencies are missing. Run npm install in the repository root." >&2
    exit 1
fi
if [[ ! -f frontend/node_modules/vite/bin/vite.js ]]; then
    echo "[ERROR] Frontend dependencies are missing. Run npm --prefix frontend ci." >&2
    exit 1
fi

PYTHON=""
for candidate in .venv/bin/activate backend/.venv/bin/activate backend/venv/bin/activate; do
    if [[ -f "$candidate" ]]; then
        # Standard venv activation scripts may read variables absent under nounset.
        set +u
        # shellcheck disable=SC1090
        source "$candidate"
        set -u
        PYTHON=python
        break
    fi
done
if [[ -z "$PYTHON" ]]; then
    if command -v python3 >/dev/null 2>&1; then PYTHON=python3
    elif command -v python >/dev/null 2>&1; then PYTHON=python
    else echo "[ERROR] Python is missing. Create .venv and install backend requirements." >&2; exit 1
    fi
fi
if ! "$PYTHON" -B -m uvicorn --version >/dev/null 2>&1; then
    echo "[ERROR] The selected Python has no Uvicorn. Install backend/requirements.txt in its environment." >&2
    exit 1
fi

export ALERT_DELIVERY_MODE="${ALERT_DELIVERY_MODE:-preview}"
export VITE_BACKEND_URL=http://127.0.0.1:8000
echo "Starting backend http://127.0.0.1:8000 and frontend http://127.0.0.1:5173"
echo "Alert delivery mode: $ALERT_DELIVERY_MODE"
echo "Press Ctrl+C to stop both. Read startup errors below; startup is not a health check."
exec "$ROOT/node_modules/.bin/concurrently" --kill-others --success all \
    --names BACKEND,FRONTEND --prefix-colors cyan,magenta \
    "cd backend && $PYTHON -B -m uvicorn main:app --host 127.0.0.1 --port 8000" \
    "npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort"
