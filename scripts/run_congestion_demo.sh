#!/usr/bin/env bash
# ==============================================================================
# Congestion Demonstration Script (Runs on background traffic host h5)
# Generates 8.5 Mbps UDP flood to saturate the 10 Mbps bottleneck link to h1.
# Automatically detects and uses iperf if available, or falls back to Python UDP.
# ==============================================================================
SERVER_IP=${1:-"10.0.0.1"}
BANDWIDTH=${2:-"8.5M"}
DURATION=${3:-"20"}

echo "=== Injecting ~8.5 Mbps background traffic towards $SERVER_IP for $DURATION seconds ==="
echo "Watch the SDN Controller terminal detect utilization >70% and trigger dynamic prioritization!"

if command -v iperf >/dev/null 2>&1; then
    echo "[CONGESTION] Using iperf UDP flood..."
    iperf -c "$SERVER_IP" -u -b "$BANDWIDTH" -t "$DURATION"
else
    echo "[CONGESTION] iperf not found, using Python high-throughput UDP flood fallback..."
    python3 -c "
import socket, time
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
payload = b'X' * 1400
t_end = time.time() + float('$DURATION')
bytes_sent = 0
t0 = time.time()
while time.time() < t_end:
    sock.sendto(payload, ('$SERVER_IP', 9999))
    bytes_sent += len(payload)
    if bytes_sent % 140000 == 0:
        time.sleep(0.001)
print(f'Sent {bytes_sent / 1e6:.2f} MB in {time.time() - t0:.1f}s')
"
fi
