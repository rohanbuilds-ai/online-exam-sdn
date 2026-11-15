#!/usr/bin/env bash
# ==============================================================================
# Run Student Examination Client (Designed for execution on hosts h2, h3, h4)
# ==============================================================================
cd "$(dirname "$0")/.."
SERVER_IP=${1:-"10.0.0.1"}
STUDENT_ID=${2:-"STU_001"}
STUDENT_NAME=${3:-"Student One"}

echo "=== Connecting Student Client ($STUDENT_NAME / $STUDENT_ID) to $SERVER_IP:5000 ==="
python3 app/client.py --server "$SERVER_IP" --port 5000 --id "$STUDENT_ID" --name "$STUDENT_NAME"
