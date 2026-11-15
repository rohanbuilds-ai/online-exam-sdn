#!/usr/bin/env bash
# ==============================================================================
# Setup Script for SDN Online Examination Network on Ubuntu Linux
# ==============================================================================
set -e

echo "=== [1/4] Updating package index ==="
sudo apt update

echo "=== [2/4] Installing system dependencies (Mininet, Open vSwitch, Python3) ==="
sudo apt install -y mininet openvswitch-switch python3 python3-pip python3-venv iperf net-tools

echo "=== [3/4] Ensuring Open vSwitch service is running ==="
sudo systemctl enable openvswitch-switch
sudo systemctl start openvswitch-switch
sudo ovs-vsctl show

echo "=== [4/4] Installing Python requirements ==="
python3 -m pip install -r requirements.txt || true

echo "=== Setup complete! ==="
echo "To verify Mininet and Open vSwitch: sudo mn --test pingall"
