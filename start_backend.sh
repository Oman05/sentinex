#!/bin/bash
# ==============================================================================
# Sentinex Backend Startup Script (Linux)
# Uses the verified Linux virtual environment with OpenCV & AI pipeline
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR/backend"

if [ -f "$PROJECT_DIR/.venv_linux/bin/activate" ]; then
    source "$PROJECT_DIR/.venv_linux/bin/activate"
    PYTHON_EXEC="$PROJECT_DIR/.venv_linux/bin/python"
    UVICORN_EXEC="$PROJECT_DIR/.venv_linux/bin/uvicorn"
elif [ -f "$PROJECT_DIR/.venv/bin/activate" ]; then
    source "$PROJECT_DIR/.venv/bin/activate"
    PYTHON_EXEC="$PROJECT_DIR/.venv/bin/python"
    UVICORN_EXEC="$PROJECT_DIR/.venv/bin/uvicorn"
else
    PYTHON_EXEC="python3"
    UVICORN_EXEC="uvicorn"
fi

echo "[SENTINEX] Starting FastAPI Backend on http://0.0.0.0:8000"
echo "[SENTINEX] Python: $($PYTHON_EXEC --version)"

export PYTHONPATH="$PROJECT_DIR/backend:$PYTHONPATH"

exec $UVICORN_EXEC app.main:app --host 0.0.0.0 --port 8000 --reload "$@"
