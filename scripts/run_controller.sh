#!/usr/bin/env bash
# ==============================================================================
# Start OpenFlow 1.3 SDN Controller with Adaptive Congestion Prioritization
# ==============================================================================
cd "$(dirname "$0")/.."
echo "=== Starting SDN OpenFlow 1.3 Controller on port 6653 ==="
python3 sdn/controller.py --host 0.0.0.0 --port 6653 --bw 10.0 --threshold 70.0
