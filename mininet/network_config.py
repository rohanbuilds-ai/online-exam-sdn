"""
Network Configuration Constants and Host/Switch Topology Mapping.
"""

CONTROLLER_IP = "127.0.0.1"
CONTROLLER_PORT = 6653
OPENFLOW_VERSION = "OpenFlow13"

# Host Definitions
HOST_CONFIGS = {
    "h1": {
        "ip": "10.0.0.1/24",
        "mac": "00:00:00:00:00:01",
        "role": "exam_server",
        "port": 5000
    },
    "h2": {
        "ip": "10.0.0.2/24",
        "mac": "00:00:00:00:00:02",
        "role": "student_client_1"
    },
    "h3": {
        "ip": "10.0.0.3/24",
        "mac": "00:00:00:00:00:03",
        "role": "student_client_2"
    },
    "h4": {
        "ip": "10.0.0.4/24",
        "mac": "00:00:00:00:00:04",
        "role": "student_client_3"
    },
    "h5": {
        "ip": "10.0.0.5/24",
        "mac": "00:00:00:00:00:05",
        "role": "background_traffic_generator"
    }
}

# Link Characteristics (10 Mbps bottleneck links)
DEFAULT_LINK_BW_MBPS = 10
DEFAULT_LINK_DELAY = "2ms"
DEFAULT_LINK_MAX_QUEUE = 100

# Open vSwitch QoS Configuration Commands (Hierarchical Token Bucket - HTB)
# Queue 0: Best Effort (1-10 Mbps; yields to guaranteed exam traffic)
# Queue 1: High-Priority Guaranteed Examination Traffic (7-10 Mbps)
QOS_CONFIG_COMMANDS = [
    # Clear any previous QoS configuration on s1-eth1 (interface connecting s1 to server h1)
    "ovs-vsctl -- --all destroy QoS -- --all destroy Queue",
    "ovs-vsctl set port s1-eth1 qos=@newqos -- "
    "--id=@newqos create QoS type=linux-htb other-config:max-rate=10000000 queues=0=@q0,1=@q1 -- "
    "--id=@q0 create Queue other-config:min-rate=1000000 other-config:max-rate=10000000 -- "
    "--id=@q1 create Queue other-config:min-rate=7000000 other-config:max-rate=10000000"
]
