#!/usr/bin/env bash
# ==============================================================================
# Start FastAPI Web Gateway (Bridges Browser to TCP Exam Server)
# ==============================================================================
cd "$(dirname "$0")/.."
echo "=== Starting FastAPI Web Gateway on port 8000 ==="
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
