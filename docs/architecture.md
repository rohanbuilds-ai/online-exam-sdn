# System and Network Architecture
## SDN-Based Online Examination Network

This document details the complete end-to-end architecture, communication flows, OpenFlow control plane interactions, and Quality of Service (QoS) enforcement mechanisms.

---

## 1. Physical and Logical Network Topology

The network consists of an OpenFlow 1.3 Open vSwitch (`s1`) connected to five Mininet virtual hosts and managed by an external custom Python OpenFlow 1.3 SDN Controller (`c0`).

```mermaid
flowchart TB
    subgraph Control_Plane ["SDN Control Plane (Port 6653)"]
        C["Custom OpenFlow 1.3 Controller<br/>• FlowManager (L2, Table-Miss, QoS)<br/>• TrafficMonitor (OFPMP_PORT_STATS)<br/>• CongestionManager (Adaptive >70%)"]
    end

    subgraph Data_Plane ["Open vSwitch Data Plane (s1)"]
        S["Open vSwitch s1<br/>OpenFlow 1.3 Engine"]
        Q0["Queue 0: Best Effort (1 - 5 Mbps)"]
        Q1["Queue 1: High Priority Exam (7 - 10 Mbps)"]
        S --- Q0
        S --- Q1
    end

    subgraph Hosts ["Mininet Virtual Hosts"]
        H1["h1 — Examination Server<br/>10.0.0.1:5000 (MAC: 00:...:01)"]
        H2["h2 — Student Client 1<br/>10.0.0.2 (MAC: 00:...:02)"]
        H3["h3 — Student Client 2<br/>10.0.0.3 (MAC: 00:...:03)"]
        H4["h4 — Student Client 3<br/>10.0.0.4 (MAC: 00:...:04)"]
        H5["h5 — Background Traffic<br/>10.0.0.5 (MAC: 00:...:05)"]
    end

    C <== "OpenFlow 1.3 (TCP 6653)" ==> S

    S <== "10 Mbps Link (Port 1)" ==> H1
    S <== "10 Mbps Link (Port 2)" ==> H2
    S <== "10 Mbps Link (Port 3)" ==> H3
    S <== "10 Mbps Link (Port 4)" ==> H4
    S <== "10 Mbps Link (Port 5)" ==> H5
```

---

## 2. Application Layer Communication Flow

The TCP application uses length-prefixed JSON framing (`!I` header + UTF-8 payload) over persistent TCP stream sockets.

```mermaid
sequenceDiagram
    autonumber
    actor Student as Student Client (h2-h4)
    participant Switch as Open vSwitch (s1)
    participant Controller as SDN Controller (c0)
    participant Server as Examination Server (h1)
    participant DB as SQLite Storage

    Note over Student,Server: Phase 1: Authentication & Session Initialization
    Student->>Server: TCP SYN (Port 5000)
    Server-->>Student: TCP SYN-ACK
    Student->>Server: AUTH_REQUEST {student_id: "STU101", name: "Alice"}
    Server->>DB: register_student() & create_session()
    Server-->>Student: AUTH_RESPONSE {status: "ACCEPTED", duration: 300, total_q: 5}

    Note over Student,Server: Phase 2: Authoritative Timed Question Cycle
    loop For each question
        Student->>Server: QUESTION_REQUEST {}
        Server-->>Student: QUESTION_DELIVERY {q_id: 1, text: "...", options: [...], remaining_sec: 295.4}
        Student->>Server: SUBMIT_ANSWER {question_id: 1, selected_option: 2}
        Server->>DB: record_answer(is_correct, points, latency)
        Server-->>Student: ANSWER_ACK {is_correct: true, points: 1, remaining_sec: 288.1}
    end

    Note over Student,Server: Phase 3: Final Grading & Session Persistence
    Server->>DB: finalize_session(score: 5, total: 5, percentage: 100.0)
    Server-->>Student: RESULT_RESPONSE {score: 5, total: 5, passed: true, reason: "COMPLETED"}
```

---

## 3. Dynamic SDN Congestion Management Workflow

The SDN controller monitors port statistics in real-time and dynamically enforces Quality of Service (QoS) queues when background congestion threatens examination traffic.

```mermaid
stateDiagram-v2
    [*] --> NORMAL : Switch Connects & Handshake

    NORMAL : State: Normal Traffic
    NORMAL : • Port Utilization < 70%
    NORMAL : • Exam traffic on Queue 0 (Best Effort)
    NORMAL : • Standard L2 Forwarding (Priority 100)

    NORMAL --> CONGESTED : Port 1 Utilization >= 70%
    
    CONGESTED : State: Dynamic Prioritization
    CONGESTED : • Install High-Priority Flow (Priority 1000)
    CONGESTED : • Match: IPv4, TCP dst_port=5000
    CONGESTED : • Action: OFPAT_SET_QUEUE 1 (7-10 Mbps)
    CONGESTED : • Background traffic throttled in Queue 0

    CONGESTED --> NORMAL : Port 1 Utilization < 35% AND Cooldown > 4.0s
```

---

## 4. Layer Responsibility Matrix

| Subsystem | Component | Key Responsibilities |
|---|---|---|
| **Application Layer** | `app.protocol` | Length-prefixed binary framing, JSON serialization, envelope validation |
| | `app.question_bank` | Question parsing, option randomization, grading explanations |
| | `app.timer` | Server-authoritative monotonic deadline tracking, auto-submission callbacks |
| | `app.storage` | Thread-safe SQLite persistence for students, sessions, answers, and scores |
| | `app.exam_manager` | Session state coordinator, timeout dispatcher, grade calculator |
| | `app.server` & `app.client` | Multi-threaded TCP server and interactive/automated student clients |
| **SDN Control Plane** | `sdn.openflow13` | OpenFlow 1.3 protocol binary packing and unpacking |
| | `sdn.flow_manager` | Table-miss, learned L2, and dynamic QoS flow mod generation |
| | `sdn.traffic_monitor` | Periodic polling of port counters, throughput & utilization calculation |
| | `sdn.congestion_manager` | Adaptive threshold detection, hysteresis cooldown, policy decision logging |
| | `sdn.controller` | Central OpenFlow listener, connection registry, policy dispatcher |
| **Data Plane / Mininet**| `mininet.topology` | Mininet network orchestration, 10 Mbps links, Open vSwitch configuration |
| | `mininet.network_config` | Network addressing, MAC mapping, Linux HTB QoS queues |
| **Benchmarking Suite** | `experiments.baseline` | Evaluates static SDN under normal and congested traffic |
| | `experiments.dynamic_sdn` | Evaluates dynamic SDN adaptive QoS prioritization |
| | `experiments.analyze_results`| Computes Jain's Fairness Index, latency percentiles, and Matplotlib plots |
