#!/usr/bin/env bash
# ==============================================================================
# Start Mininet Network Topology with Open vSwitch and Linux HTB QoS Queues
# ==============================================================================
cd "$(dirname "$0")/.."
echo "=== Cleaning up any previous Mininet or OVS states ==="
sudo mn -c 2>/dev/null || true
sudo ovs-vsctl -- --all destroy QoS -- --all destroy Queue 2>/dev/null || true

echo "=== Starting Mininet Network Topology ==="
sudo python3 mininet/topology.py
