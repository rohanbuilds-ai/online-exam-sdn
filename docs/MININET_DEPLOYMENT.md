# SDN-Based Online Examination Network — Ubuntu Mininet Deployment Guide

## 1. Executive Overview & Data Path Architecture

This guide details the complete deployment and verification procedure for the **SDN-Based Online Examination Network** in an Ubuntu Linux environment running Mininet 2.3+ and Open vSwitch (OVS).

### Real Traffic Path Across Open vSwitch

To preserve hardware and kernel-level QoS packet scheduling, the web application runs inside the Mininet virtual network namespaces:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       HOST WORKSTATION / WEB BROWSER                        │
│                         http://<VM_IP>:8000                                 │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP / WebSocket (Port 8000)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 MININET VIRTUAL NETWORK NAMESPACE: h2 (Student)             │
│   FastAPI Web Gateway (api/main.py)                                         │
│   - Receives student HTTP requests                                          │
│   - Opens persistent TCP socket to 10.0.0.1:5000                            │
│   - Transmits length-prefixed JSON frames (!I header + UTF-8 payload)       │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ TCP Stream (Source: 10.0.0.2:*, Dest: 10.0.0.1:5000)
                                       │ Interface: s1-eth2 (Port 2)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DATA PLANE: OPEN vSWITCH s1                            │
│   OpenFlow 1.3 Flow Table (DPID: 0000000000000001)                          │
│                                                                             │
│   [Normal Condition]                                                        │
│     Match: in_port=2, dl_dst=00:00:00:00:00:01                              │
│     Action: output:1 (Queue 0: Best Effort, 1-5 Mbps)                       │
│                                                                             │
│   [Congested Condition - Dynamic SDN QoS Active]                            │
│     Match: tcp, nw_dst=10.0.0.1, tp_dst=5000 (Priority 1000)                │
│     Action: set_queue:1, output:1 (Queue 1: Exam Priority, 7-10 Mbps)       │
│                                                                             │
│   *Competing Traffic from h5 (iperf UDP 8.5 Mbps) stays trapped in Queue 0  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ 10 Mbps Bottleneck Link (Port 1 / s1-eth1)
                                       │ Priority Queue 1 guarantees minimum 7 Mbps
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 MININET VIRTUAL NETWORK NAMESPACE: h1 (Server)              │
│   TCP Examination Daemon (app/server.py)                                    │
│   - Authoritative countdown timer (monotonic clock)                         │
│   - Question delivery & answer grading                                      │
│   - Thread-safe SQLite result archiving (exam_records.db)                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                       ▲
                                       │ OpenFlow 1.3 (TCP 6653)
                                       │ Statistics Polling & Flow-Mod Push
┌──────────────────────────────────────┴──────────────────────────────────────┐
│                    CONTROL PLANE: SDN CONTROLLER (c0)                       │
│   Pure Python OpenFlow 1.3 Controller (sdn/controller.py)                   │
│   - Periodic OFPMP_PORT_STATS multipart polling (1.0s interval)             │
│   - Rate calculation: Util% = (delta_bytes * 8) / (delta_t * link_bw)       │
│   - Congestion threshold detection (>70.0% link capacity)                   │
│   - Pushes priority=1000 flow-mod with OFPAT_SET_QUEUE 1                    │
│   - Hysteresis recovery (<35.0%) with OFPFC_DELETE rule removal             │
└─────────────────────────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **Windows vs. Ubuntu Mininet Scope Distinction:**
> - **Windows-Local Execution**: Validates the application presentation layer, FastAPI HTTP/WebSocket gateway, TCP adapter framing, and SQLite persistence over the local loopback interface (`127.0.0.1`). It does **not** simulate kernel queuing or packet drops.
> - **Ubuntu Mininet Execution**: Validates physical Linux Hierarchical Token Bucket (HTB) queuing disciplines, Open vSwitch OpenFlow 1.3 packet matching, bandwidth saturation via `iperf`, and hardware-realistic latency reductions.

---

## 2. Mininet Network Addressing & Port Mapping

| Host / Node | IP Address | MAC Address | Switch Interface | Physical Queue Policy | Role |
|---|---|---|---|---|---|
| **c0** | `127.0.0.1:6653` | — | Loopback / Out-of-band | — | Custom Python OpenFlow 1.3 Controller |
| **s1** | — | `00:00:00:00:00:01` (DPID) | Kernel Datapath | Queue 0 (Best-effort), Queue 1 (QoS Priority) | Open vSwitch with Linux HTB queuing |
| **h1** | `10.0.0.1/24` | `00:00:00:00:00:01` | `s1-eth1` (Port 1) | 10 Mbps bottleneck link | Central Examination Daemon (`app/server.py`) |
| **h2** | `10.0.0.2/24` | `00:00:00:00:00:02` | `s1-eth2` (Port 2) | 10 Mbps link | Student 1 / Gateway Host (`api/main.py`) |
| **h3** | `10.0.0.3/24` | `00:00:00:00:00:03` | `s1-eth3` (Port 3) | 10 Mbps link | Student 2 Client (`app/client.py`) |
| **h4** | `10.0.0.4/24` | `00:00:00:00:00:04` | `s1-eth4` (Port 4) | 10 Mbps link | Student 3 Client (`app/client.py`) |
| **h5** | `10.0.0.5/24` | `00:00:00:00:00:05` | `s1-eth5` (Port 5) | 10 Mbps link | Background Congestion Generator (`iperf` UDP) |

---

## 3. Ubuntu VM Step-by-Step Deployment Procedure

### Step 1: Install Dependencies
Inside your Ubuntu terminal:
```bash
cd ~/online-exam-sdn
chmod +x scripts/*.sh
sudo ./scripts/setup_ubuntu.sh
```
This verifies:
- Python 3.8+ with `pip`
- Mininet 2.3+ (`mn --version`)
- Open vSwitch (`ovs-vsctl --version`)
- `iperf` traffic generator
- Required Python modules from `requirements.txt` and `api/requirements.txt`

---

### Step 2: Start the Pure-Python SDN Controller (Terminal 1)
```bash
cd ~/online-exam-sdn
python3 -m sdn.controller --host 0.0.0.0 --port 6653 --bw 10.0 --threshold 70.0 --recovery 35.0
```
**Expected Output:**
```
[INFO] [SDNController] OpenFlow 1.3 Controller listening on 0.0.0.0:6653
[INFO] [SDNController] Parameters: Link Bandwidth=10.0 Mbps, Congestion Threshold=70.0%, Recovery=35.0%
```

---

### Step 3: Launch the Mininet Topology (Terminal 2)
In a second terminal, launch the custom topology with Linux HTB QoS queues:
```bash
cd ~/online-exam-sdn
sudo python3 -m mininet.topology
```
**Expected Output:**
```
*** Creating network
*** Adding controller c0
*** Adding hosts: h1 h2 h3 h4 h5
*** Adding switch s1
*** Configuring Open vSwitch s1 with OpenFlow 1.3...
*** Configuring Linux HTB Queues on s1-eth1:
    - Queue 0: 1 - 5 Mbps (Best-Effort)
    - Queue 1: 7 - 10 Mbps (Exam Priority QoS)
*** Starting CLI:
mininet>
```

---

### Step 4: Start the Authoritative Examination Daemon on Host `h1`
At the Mininet prompt:
```bash
mininet> h1 python3 -m app.server --host 10.0.0.1 --port 5000 --duration 600 --questions 5 &
```
Verify the server is listening:
```bash
mininet> h1 netstat -tuln | grep 5000
tcp  0  0 10.0.0.1:5000  0.0.0.0:*  LISTEN
```

---

### Step 5: Start the FastAPI Web Gateway on Host `h2`
To allow external browser access from the host OS, run the FastAPI gateway bound to `0.0.0.0`:
```bash
mininet> h2 uvicorn api.main:app --host 0.0.0.0 --port 8000 &
```
Configure environment variables if needed:
```bash
mininet> h2 export EXAM_SERVER_HOST=10.0.0.1
mininet> h2 export EXAM_SERVER_PORT=5000
mininet> h2 export ADMIN_PASSWORD=your_secure_admin_password_here
mininet> h2 export SESSION_COOKIE_SECURE=false
```

---

### Step 6: Connect Host Browser to the Prototype
If using VirtualBox:
- Ensure VirtualBox Port Forwarding is set:
  - `Host Port: 8000` → `Guest Port: 8000`
  - `Host Port: 5173` → `Guest Port: 5173`
- Or access the VM's Host-Only adapter IP (e.g. `http://192.168.56.101:8000`).

Open your host browser:
- **Web Prototype**: `http://localhost:8000` (Served as pre-built SPA bundle from `frontend/dist`)
- **Interactive Swagger Docs**: `http://localhost:8000/docs`

---

### Step 7: Induce Network Congestion & Observe Dynamic QoS
1. In Mininet, generate 8.5 Mbps of background UDP traffic from host `h5` to host `h1` across the 10 Mbps bottleneck link:
   ```bash
   mininet> h5 bash scripts/run_congestion_demo.sh 10.0.0.1 8.5M 30
   ```
2. **Observe Controller Console (Terminal 1)**:
   ```
   [WARNING] [SDNCongestionManager] [SDN POLICY TRIGGER] Port 1 -> CONGESTION_DETECTED: Utilization reached 88.5%. Enforcing Priority Queue 1 for Exam Traffic.
   [INFO] [SDNController] Installed High-Priority Flow (priority=1000): TCP dst 5000 -> OFPAT_SET_QUEUE 1
   ```
3. **Verify Open vSwitch Flow Table**:
   ```bash
   mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s1
   ```
   Output confirms the active rule:
   ```
   cookie=0x0, duration=4.2s, table=0, n_packets=82, n_bytes=9840, priority=1000,tcp,nw_dst=10.0.0.1,tp_dst=5000 actions=set_queue:1,output:1
   ```
4. **Observe Student Traffic in Web UI**:
   - The Student Portal continues answering questions seamlessly without dropped connections or timeouts.
   - The NOC Dashboard indicates **CONGESTED** status and shows the policy state transition in real time.

---

### Step 8: Clean Teardown
When finished, exit Mininet and purge virtual interfaces:
```bash
mininet> exit
sudo mn -c
```
Kill any remaining controller or server background processes:
```bash
sudo pkill -f sdn.controller
sudo pkill -f app.server
sudo pkill -f uvicorn
```
