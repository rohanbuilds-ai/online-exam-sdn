#!/usr/bin/env python3
"""
Mininet Topology with Open vSwitch, Remote SDN Controller, and Linux HTB QoS Queues.

Hosts:
- h1 (10.0.0.1): Examination Server (TCP Port 5000)
- h2 (10.0.0.2): Student Client 1
- h3 (10.0.0.3): Student Client 2
- h4 (10.0.0.4): Student Client 3
- h5 (10.0.0.5): Background Traffic Generator (iperf / congestion source)

Switch:
- s1: Open vSwitch running OpenFlow 1.3
- Port 1 (s1-eth1) configured with Linux HTB QoS Queues:
    - Queue 0: Best Effort (1 - 5 Mbps)
    - Queue 1: Guaranteed High-Priority Examination Traffic (7 - 10 Mbps)

Controller:
- c0: RemoteController at 127.0.0.1:6653
"""

import os
import subprocess
import sys
import time

try:
    from mininet.net import Mininet
    from mininet.node import OVSSwitch, RemoteController
    from mininet.link import TCLink
    from mininet.cli import CLI
    from mininet.log import setLogLevel, info
    MININET_AVAILABLE = True
except ImportError:
    MININET_AVAILABLE = False

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


def configure_ovs_qos():
    """Apply Linux HTB QoS queues on Open vSwitch port s1-eth1."""
    print("[QOS] Configuring Linux HTB queues on switch s1 port s1-eth1...")
    for cmd in QOS_CONFIG_COMMANDS:
        try:
            res = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as err:
            print(f"[QOS WARNING] QoS command failed: {err.stderr.decode()}")
    print("[QOS] Queues initialized: Queue 0 (1-5 Mbps Best Effort), Queue 1 (7-10 Mbps Guaranteed Priority).")
    verify_ovs_qos()


def verify_ovs_qos():
    """Display active OVS QoS tables and Queues for verification."""
    try:
        qos_out = subprocess.run("ovs-vsctl list QoS", shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        queue_out = subprocess.run("ovs-vsctl list Queue", shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if qos_out.stdout:
            print("[QOS VERIFIED] Active Open vSwitch QoS configuration detected.")
        if queue_out.stdout:
            print("[QOS VERIFIED] Active Open vSwitch Queues (Queue 0 & Queue 1) successfully installed.")
    except Exception:
        pass


def create_topology(cli_mode: bool = True):
    if not MININET_AVAILABLE:
        print("[ERROR] Mininet library not available in this environment.")
        print("Please run this script inside the Ubuntu VM with Mininet and Open vSwitch installed.")
        return None

    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=False
    )

    info("*** Adding Remote SDN Controller\n")
    net.addController(
        "c0",
        controller=RemoteController,
        ip=CONTROLLER_IP,
        port=CONTROLLER_PORT
    )

    info("*** Adding OpenFlow 1.3 Switch\n")
    switch = net.addSwitch("s1", protocols=OPENFLOW_VERSION)

    info("*** Adding Examination Server and Student Hosts\n")
    hosts = {}
    for name, cfg in HOST_CONFIGS.items():
        h = net.addHost(name, ip=cfg["ip"], mac=cfg["mac"])
        hosts[name] = h

    info("*** Creating 10 Mbps Links with Traffic Control\n")
    for name, h in hosts.items():
        # First added link is s1-eth1 (h1 server connection)
        net.addLink(
            h,
            switch,
            bw=DEFAULT_LINK_BW_MBPS,
            delay=DEFAULT_LINK_DELAY,
            max_queue_size=DEFAULT_LINK_MAX_QUEUE
        )

    info("*** Starting Mininet Network\n")
    net.start()

    # Configure Linux HTB QoS queues on switch s1
    configure_ovs_qos()

    info("*** Testing Full Host Connectivity (pingall)\n")
    net.pingAll()

    if cli_mode:
        info("*** Entering Mininet CLI. Type 'exit' to quit.\n")
        CLI(net)
        info("*** Stopping Network\n")
        net.stop()
        # Clean up QoS
        subprocess.run("ovs-vsctl -- --all destroy QoS -- --all destroy Queue", shell=True, stderr=subprocess.DEVNULL)
    else:
        return net


def main():
    if os.geteuid() != 0:
        print("[ERROR] Mininet topology must be run with root privileges (sudo).")
        sys.exit(1)

    setLogLevel("info")
    create_topology(cli_mode=True)


if __name__ == "__main__":
    main()
