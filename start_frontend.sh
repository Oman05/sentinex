#!/bin/bash
# ==============================================================================
# Sentinex Frontend Startup Script
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR/frontend"

echo "[SENTINEX] Starting Vite Frontend on http://localhost:5173"
exec npm run dev -- --host 0.0.0.0
