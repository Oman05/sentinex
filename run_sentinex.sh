#!/bin/bash
# ==============================================================================
# Sentinex Full Launch Script
# Starts the FastAPI backend + Webcam Live Analysis (with GUI display)
# ==============================================================================

set -e
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect venv
if [ -f "$PROJECT_DIR/.venv_linux/bin/activate" ]; then
    VENV_DIR="$PROJECT_DIR/.venv_linux"
elif [ -f "$PROJECT_DIR/.venv/bin/activate" ]; then
    VENV_DIR="$PROJECT_DIR/.venv"
else
    echo "[ERROR] No virtual environment found. Run: python3 -m venv .venv_linux && .venv_linux/bin/pip install -r requirements.txt"
    exit 1
fi

PYTHON="$VENV_DIR/bin/python"
UVICORN="$VENV_DIR/bin/uvicorn"
export PYTHONPATH="$PROJECT_DIR/backend:$PYTHONPATH"

echo "======================================================"
echo "  Sentinex – Full System Launcher"
echo "======================================================"
echo "  Project  : $PROJECT_DIR"
echo "  Python   : $($PYTHON --version)"
echo "  Venv     : $VENV_DIR"
echo "======================================================"

# --- Start Backend ---
echo ""
echo "[1/2] Starting FastAPI backend on http://0.0.0.0:8000 ..."
cd "$PROJECT_DIR/backend"
$UVICORN app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "      Backend PID: $BACKEND_PID"
sleep 2

# --- Start Webcam Analysis ---
echo ""
echo "[2/2] Starting Webcam Live Analysis (GUI window) ..."
cd "$PROJECT_DIR"

# Parse optional args
CAMERA="${SENTINEX_CAMERA:-0}"
FPS="${SENTINEX_FPS:-2.0}"
THRESHOLD="${SENTINEX_THRESHOLD:-0.70}"
HEADLESS="${SENTINEX_HEADLESS:-}"

echo "      Camera   : /dev/video$CAMERA"
echo "      FPS      : $FPS"
echo "      Threshold: $THRESHOLD"
echo "      Headless : ${HEADLESS:-no (GUI window)}"
echo ""

if [ -n "$HEADLESS" ]; then
    $PYTHON webcam_live_analysis.py --camera "$CAMERA" --fps "$FPS" --threshold "$THRESHOLD" --no-display
else
    $PYTHON webcam_live_analysis.py --camera "$CAMERA" --fps "$FPS" --threshold "$THRESHOLD"
fi

# Cleanup backend on exit
echo ""
echo "[Shutdown] Stopping backend (PID $BACKEND_PID)..."
kill $BACKEND_PID 2>/dev/null || true
echo "[Done]"

