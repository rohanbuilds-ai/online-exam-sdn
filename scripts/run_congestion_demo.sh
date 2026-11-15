#!/usr/bin/env bash
# ==============================================================================
# Congestion Demonstration Script (Runs on background traffic host h5)
# Generates 8.5 Mbps UDP flood to saturate the 10 Mbps bottleneck link to h1.
# ==============================================================================
SERVER_IP=${1:-"10.0.0.1"}
BANDWIDTH=${2:-"8.5M"}
DURATION=${3:-"20"}

echo "=== Injecting $BANDWIDTH background traffic towards $SERVER_IP for $DURATION seconds ==="
echo "Watch the SDN Controller terminal detect utilization >70% and trigger dynamic prioritization!"
iperf -c "$SERVER_IP" -u -b "$BANDWIDTH" -t "$DURATION"
