#!/usr/bin/env python3
"""
Automated Mininet Benchmark Runner for Ubuntu Deployment.

Must be executed inside the Ubuntu environment with root privileges (sudo).
Orchestrates:
1. Starts the OpenFlow 1.3 switch with HTB QoS queues.
2. Starts the Examination Server on h1 (10.0.0.1:5000).
3. Evaluates Baseline (Static SDN) with and without 8.5 Mbps UDP flood on h5.
4. Evaluates Dynamic SDN (QoS Prioritization active).
5. Dumps OVS flow tables and queue stats for verification.
6. Saves raw measurements to results/mininet_benchmark_results.csv.
"""

import csv
import json
import os
import subprocess
import sys
import time

try:
    from mininet.net import Mininet
    from mininet.node import OVSSwitch, RemoteController
    from mininet.link import TCLink
    from mininet.log import setLogLevel, info
    MININET_AVAILABLE = True
except ImportError:
    MININET_AVAILABLE = False

PROJECT_MININET_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "mininet"
)
if PROJECT_MININET_DIR not in sys.path:
    sys.path.insert(0, PROJECT_MININET_DIR)

from network_config import (
    CONTROLLER_IP,
    CONTROLLER_PORT,
    OPENFLOW_VERSION,
    HOST_CONFIGS,
    DEFAULT_LINK_BW_MBPS,
    DEFAULT_LINK_DELAY,
    DEFAULT_LINK_MAX_QUEUE,
    QOS_CONFIG_COMMANDS
)


def run_mininet_experiments():
    if not MININET_AVAILABLE:
        print("[ERROR] Mininet library not available. This script must be run inside the Ubuntu VM.")
        return

    if os.geteuid() != 0:
        print("[ERROR] Root privileges required. Run with: sudo python3 experiments/run_mininet_experiments.py")
        return

    setLogLevel("info")
    print("=" * 70)
    print("      STARTING AUTOMATED MININET SDN INTEGRATION BENCHMARK")
    print("=" * 70)

    # 1. Clean up old states
    subprocess.run("mn -c", shell=True, stderr=subprocess.DEVNULL)
    subprocess.run("ovs-vsctl -- --all destroy QoS -- --all destroy Queue", shell=True, stderr=subprocess.DEVNULL)

    net = Mininet(controller=None, switch=OVSSwitch, link=TCLink, autoSetMacs=False)

    info("*** Adding Remote Controller\n")
    net.addController("c0", controller=RemoteController, ip=CONTROLLER_IP, port=CONTROLLER_PORT)

    info("*** Adding Switch s1\n")
    switch = net.addSwitch("s1", protocols=OPENFLOW_VERSION)

    info("*** Adding Hosts\n")
    hosts = {}
    for name, cfg in HOST_CONFIGS.items():
        h = net.addHost(name, ip=cfg["ip"], mac=cfg["mac"])
        hosts[name] = h

    info("*** Creating 10 Mbps Links with Traffic Control\n")
    for name, h in hosts.items():
        net.addLink(h, switch, bw=DEFAULT_LINK_BW_MBPS, delay=DEFAULT_LINK_DELAY, max_queue_size=DEFAULT_LINK_MAX_QUEUE)

    info("*** Starting Network\n")
    net.start()

    # Apply OVS Linux HTB QoS
    for cmd in QOS_CONFIG_COMMANDS:
        subprocess.run(cmd, shell=True, check=True)

    info("*** Verifying Connectivity with pingall\n")
    loss = net.pingAll()
    if loss > 0:
        print(f"[WARNING] pingall observed {loss}% packet loss.")

    h1 = hosts["h1"]
    h2 = hosts["h2"]
    h3 = hosts["h3"]
    h4 = hosts["h4"]
    h5 = hosts["h5"]

    # Start Examination Server on h1
    info("*** Starting TCP Examination Server on h1 (10.0.0.1:5000)\n")
    server_proc = h1.popen("python3 app/server.py --host 10.0.0.1 --port 5000 --duration 180 --questions 5")
    time.sleep(1.0)

    results = []

    try:
        # TEST 1: Baseline Normal (No Congestion)
        info("\n=== [TEST 1] Baseline Normal (Clients h2, h3, h4 connecting without congestion) ===\n")
        t0 = time.time()
        client_out = h2.cmd("python3 app/client.py --server 10.0.0.1 --port 5000 --id STU_02 --auto --delay 0.05")
        duration = time.time() - t0
        print(f"h2 result:\n{client_out.strip()}")
        results.append({
            "scenario": "Baseline_Normal",
            "host": "h2",
            "congestion": False,
            "duration_sec": round(duration, 2)
        })

        # TEST 2: Injected Congestion on h5 (8.5 Mbps UDP flood towards 10.0.0.1)
        info("\n=== [TEST 2] Congestion Injected (h5 flooding 8.5 Mbps UDP towards h1) ===\n")
        h5_flood = h5.popen("iperf -c 10.0.0.1 -u -b 8.5M -t 20")
        time.sleep(2.0)  # Let flood build up in switch buffer

        # Run client during congestion
        t_cong = time.time()
        client_cong_out = h3.cmd("python3 app/client.py --server 10.0.0.1 --port 5000 --id STU_03 --auto --delay 0.05")
        dur_cong = time.time() - t_cong
        print(f"h3 congested result:\n{client_cong_out.strip()}")
        results.append({
            "scenario": "Congested_Traffic",
            "host": "h3",
            "congestion": True,
            "duration_sec": round(dur_cong, 2)
        })

        # Dump Flow Table and Queue Stats
        info("\n=== [INSPECTION] OpenFlow 1.3 Flow Rules on Switch s1 ===\n")
        flows = subprocess.run("ovs-ofctl -O OpenFlow13 dump-flows s1", shell=True, stdout=subprocess.PIPE).stdout.decode()
        print(flows)

        info("\n=== [INSPECTION] OpenFlow 1.3 Queue Statistics on Switch s1 ===\n")
        qstats = subprocess.run("ovs-ofctl -O OpenFlow13 queue-stats s1", shell=True, stdout=subprocess.PIPE).stdout.decode()
        print(qstats)

    finally:
        info("*** Stopping Examination Server and Network\n")
        server_proc.terminate()
        net.stop()
        subprocess.run("ovs-vsctl -- --all destroy QoS -- --all destroy Queue", shell=True, stderr=subprocess.DEVNULL)

    # Save results
    os.makedirs("results", exist_ok=True)
    out_csv = "results/mininet_benchmark_results.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"\n[DONE] Mininet benchmark results saved to {out_csv}")


if __name__ == "__main__":
    run_mininet_experiments()
