#!/usr/bin/env bash
# ==============================================================================
# Run Examination Server (Designed for execution on host h1 or localhost)
# ==============================================================================
cd "$(dirname "$0")/.."
echo "=== Starting TCP Examination Server ==="
python3 app/server.py --host 0.0.0.0 --port 5000 --duration 300 --questions 5
