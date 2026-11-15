# Viva Defense and Technical Interview Guide
## SDN-Based Online Examination Network

This guide provides deep technical explanations, networking fundamentals, architectural justifications, and likely examination/viva questions to help you independently explain and defend this project.

---

## 1. Core Architectural Concepts

### A. Why Software-Defined Networking (SDN)?
- **Traditional Networks**: The control plane (routing decisions, Spanning Tree, OSPF/BGP) and data plane (hardware packet forwarding) are co-located inside every individual router or switch. Network management is distributed, rigid, and vendor-dependent.
- **SDN**: Decouples the **control plane** (centralized intelligence in software) from the **data plane** (programmable OpenFlow switches). The controller maintains a global view of network state, enabling dynamic traffic steering, real-time telemetry, and adaptive Quality of Service (QoS).

### B. OpenFlow 1.3 Communication Lifecycle
1. **TCP Connection**: Switch initiates TCP connection to controller port 6653.
2. **OFPT_HELLO (type 0)**: Both parties exchange highest supported OpenFlow version (wire version 4 = OpenFlow 1.3).
3. **OFPT_FEATURES_REQUEST (type 5) & REPLY (type 6)**: Controller queries switch Datapath ID (DPID), table count, buffer count, and capabilities.
4. **Table-Miss Rule Installation (OFPT_FLOW_MOD, type 14)**: Controller installs default rule at `priority=0` instructing the switch to forward all unmatched packets to the controller (`OFPP_CONTROLLER`) encapsulated in `OFPT_PACKET_IN`.
5. **OFPT_PACKET_IN (type 10)**: Switch sends unknown packets to controller. Controller parses Ethernet, IP, TCP headers, learns source MACs, and calculates out ports.
6. **OFPT_FLOW_MOD & PACKET_OUT (type 13)**: Controller installs forwarding rules (`priority=100`) and outputs the packet.

### C. Traffic Monitoring via Multipart Port Statistics
- OpenFlow 1.3 provides **OFPT_MULTIPART_REQUEST (type 18)** with `OFPMP_PORT_STATS` (subtype 4).
- Switch responds with **OFPT_MULTIPART_REPLY (type 19)** containing cumulative 64-bit counters: `tx_bytes`, `rx_bytes`, `tx_packets`, `rx_packets`, `tx_dropped`, `rx_dropped`.
- The controller periodically polls ports (e.g. every 2.0 seconds) and calculates:
  $$\text{Throughput (bps)} = \frac{(\text{bytes}_{t_2} - \text{bytes}_{t_1}) \times 8}{t_2 - t_1}$$
  $$\text{Link Utilization} \% = \left(\frac{\text{Throughput}}{\text{Link Capacity (10 Mbps)}}\right) \times 100\%$$

### D. Quality of Service (QoS) & Congestion Prioritization
- OpenFlow rules alone do not magically prevent packet drops in congested buffers.
- In Linux/Open vSwitch, bandwidth reservation requires **Traffic Control (tc)** with **Hierarchical Token Bucket (HTB)** queuing disciplines.
- Switch port `s1-eth1` is configured with:
  - **Queue 0**: Best Effort (min 1 Mbps, max 5 Mbps).
  - **Queue 1**: Guaranteed High Priority (min 7 Mbps, max 10 Mbps).
- When link utilization exceeds **70%**, the controller's **CongestionManager** detects congestion and installs high-priority OpenFlow rules (`priority=1000`) matching `eth_type=0x0800`, `ip_proto=6`, `tcp_dst=5000` with action **OFPAT_SET_QUEUE (type 21, queue_id=1)**.
- Examination packets bypass the congested Queue 0, preventing packet loss and eliminating bufferbloat.

---

## 2. TCP Socket Programming & Concurrency

### A. Reliable Message Framing
- **Stream Nature of TCP**: TCP is a continuous byte-stream protocol, not a message-based protocol. A single `sock.recv(4096)` call can return partial messages or multiple messages glued together.
- **Solution**: Length-prefixed framing. Every packet starts with a 4-byte big-endian unsigned integer (`struct.pack("!I", len(payload))`) indicating exact JSON payload size. The receiver reads exactly 4 bytes, extracts length $L$, and loops until all $L$ bytes arrive.

### B. Server-Authoritative Timer
- A client-side countdown timer can be tampered with (e.g., freezing the browser/client clock).
- The server maintains monotonic clock deadlines (`time.monotonic()`) inside `StudentSession` and `ExamTimer`. If a student submits an answer after the deadline, the server rejects it and triggers automatic submission.

### C. Concurrency & Thread Safety
- The server spawns a dedicated worker thread per student (`threading.Thread`).
- SQLite writes are synchronized using Python's `threading.RLock()` and Write-Ahead Logging (WAL mode), eliminating database lock contention during concurrent submissions.

---

## 3. Performance Metrics & Jain's Fairness Index

### A. Why Jain's Fairness Index?
$$\mathcal{J}(x_1, x_2, \dots, x_n) = \frac{\left(\sum_{i=1}^n x_i\right)^2}{n \cdot \sum_{i=1}^n x_i^2}$$
- **Interpretation**: Measures equality of service across $n$ students.
  - $\mathcal{J} = 1.0$: Perfectly fair (all students receive identical service rates).
  - $\mathcal{J} = 1/n$: Worst-case starvation (one client gets all resources, others get zero).
- In our project, $x_i$ is per-client throughput (service rate $\text{req/s}$). Under Dynamic SDN, $\mathcal{J} > 0.98$, proving that no student suffers unfair timeouts even under high network congestion.

---

## 4. Top 15 Viva Questions and Answers

#### Q1: What happens during the OpenFlow 1.3 handshake?
**Answer**: When the OVS switch connects to the controller on TCP port 6653, both exchange `OFPT_HELLO` messages to agree on version 1.3 (wire version 4). The controller sends `OFPT_FEATURES_REQUEST` and the switch replies with `OFPT_FEATURES_REPLY` containing DPID and capabilities. The controller then installs a `table-miss` rule (`priority=0`) that directs unmatched traffic to the controller via `OFPT_PACKET_IN`.

#### Q2: How does the controller know when the network is congested?
**Answer**: The controller runs a periodic background polling thread that sends `OFPT_MULTIPART_REQUEST` (`OFPMP_PORT_STATS`) to switch `s1`. The switch replies with cumulative byte counters. The controller calculates $\Delta \text{bytes} / \Delta t$ to derive transmission rate in Mbps and compares it to the 10 Mbps link bandwidth. If utilization exceeds the configurable 70% threshold, the congestion manager enters `CONGESTED` state.

#### Q3: How does the controller prioritize examination traffic?
**Answer**: The controller installs an OpenFlow flow mod rule with high priority (`priority=1000`) matching IPv4 TCP traffic on destination port 5000 (`tcp_dst=5000`). It attaches two instructions: `OFPAT_SET_QUEUE` (queue_id=1) and `OFPAT_OUTPUT` (port 1). In the Linux kernel, Open vSwitch HTB queue 1 guarantees 7-10 Mbps of dedicated bandwidth, isolating exam packets from background traffic.

#### Q4: Why did you use length-prefixed framing instead of newline delimiters?
**Answer**: While newline delimiters work for simple single-line strings, they fail if JSON payloads contain newlines or escaped strings. Length-prefixed framing (`[4-byte Big-Endian Length][Binary UTF-8 Payload]`) guarantees unambiguous packet boundary demarcation over TCP streams regardless of payload content.

#### Q5: How do you prevent timer cheating by students?
**Answer**: The examination timer is completely server-authoritative. The server records `start_time = time.monotonic()` when the session is initialized. Every answer submission verifies `current_time - start_time <= duration`. If the deadline passes, any subsequent answer is rejected, and the server automatically finalizes the exam with `TIME_EXPIRED`.

#### Q6: What is bufferbloat and how did your project mitigate it?
**Answer**: Bufferbloat occurs when large network buffers fill with bulk background traffic, causing high queueing delays (often hundreds of milliseconds) for latency-sensitive packets. Without QoS, baseline exam latency surged from 15 ms to over 445 ms. With Dynamic SDN QoS queue separation, exam traffic is placed in an independent queue with dedicated token bucket rate, keeping latency under 37 ms.

#### Q7: What is hysteresis in congestion control?
**Answer**: Hysteresis prevents rapid policy flapping. The controller triggers congestion mode at 70% utilization, but requires utilization to drop below 35% (the recovery threshold) for at least 4.0 seconds (cooldown period) before restoring baseline settings.

#### Q8: What database is used and how is thread-safety ensured?
**Answer**: SQLite 3 is used for persistent storage (`exam_records.db`). Tables store student profiles, sessions, per-question answers, and final graded scores. Thread safety is guaranteed using Python's `threading.RLock()` and SQLite's Write-Ahead Logging (WAL mode).

#### Q9: What are the fields in an OpenFlow 1.3 Flow Mod message?
**Answer**: Header (8 bytes), cookie (8 bytes), cookie mask (8 bytes), table_id (1 byte), command (1 byte: ADD, MODIFY, DELETE), idle_timeout (2 bytes), hard_timeout (2 bytes), priority (2 bytes), buffer_id (4 bytes), out_port (4 bytes), out_group (4 bytes), flags (2 bytes), match structure (OXM TLVs), and instructions.

#### Q10: How does Jain's Fairness Index prove fairness?
**Answer**: It measures variance across normalized allocations. In congested baseline tests, unfair queue drops caused fairness to fall to 0.94. Dynamic SDN restored fairness to >0.98, showing all students experienced uniform response times.

#### Q11: What Mininet switches and links are used?
**Answer**: We use Open vSwitch (`OVSSwitch`) communicating over `OpenFlow13` and `TCLink` (Traffic Control Link) configured with 10 Mbps bandwidth, 2 ms propagation delay, and a maximum queue size of 100 packets.

#### Q12: How do you demonstrate background traffic injection?
**Answer**: Host `h5` generates UDP flood traffic using `iperf -c 10.0.0.1 -u -b 8.5M -t 20`, saturating 85% of the 10 Mbps link to the exam server. The controller immediately detects the spike and activates Queue 1 prioritization.

#### Q13: What is the purpose of the table-miss rule?
**Answer**: In OpenFlow 1.3, switches do not automatically forward unknown packets unless explicitly told. The table-miss rule matches any packet at the lowest priority (`priority=0`) and sends it to the controller (`OFPP_CONTROLLER`), allowing dynamic MAC learning.

#### Q14: How does the client handle connection failures?
**Answer**: Socket operations have configurable timeouts (`settimeout(15.0)`). Connection dropouts or server crashes trigger clean exception handling, preventing the client or server from hanging indefinitely.

#### Q15: What would happen if we used Ryu or POX instead of the custom controller?
**Answer**: Ryu relies on Python `eventlet` / `greenlet`, which are broken on modern Python 3.10+ and Ubuntu 22.04/24.04. Our controller is pure Python 3 standard library, has zero external dependencies, and gives total, auditable control over binary OpenFlow 1.3 message structures.
