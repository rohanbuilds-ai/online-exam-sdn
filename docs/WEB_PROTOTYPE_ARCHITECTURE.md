# SDN-Based Online Examination Network — Web Prototype Architecture & Deployment Guide

## 1. Overall System Architecture

The Online Examination Network is engineered as a three-tier architecture:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TIER 1: PRESENTATION LAYER                        │
│                   React 18 + TypeScript + Vite + Tailwind CSS               │
│                                                                             │
│  [Student Exam Portal]       [Admin Dashboard]       [SDN Network Ops NOC]  │
│    - Auth & instructions       - Results table          - Topology SVG map  │
│    - Authoritative timer       - Active TCP streams     - Live queue states │
│    - Question navigator        - SQLite analytics       - Benchmark charts  │
└───────────────────────┬──────────────────────────────────▲──────────────────┘
                        │ HTTP / WebSocket                 │
                        ▼ (Port 8000)                      │ Telemetry Feed
┌──────────────────────────────────────────────────────────┴──────────────────┐
│                            TIER 2: WEB ADAPTER LAYER                        │
│                   FastAPI Asynchronous Gateway (api/main.py)                │
│                                                                             │
│  - Persistent TcpExamAdapter per active candidate session                   │
│  - In-memory thread-safe SessionStore (UUID4 tracking)                      │
│  - Length-prefixed framing serializer / deserializer                        │
│  - SDN Telemetry Store with staleness and disconnected detection            │
│  - OpenAPI / Swagger documentation (/docs)                                  │
└───────────────────────┬──────────────────────────────────▲──────────────────┘
                        │ TCP Stream (Port 5000)           │
                        │ Traversing Open vSwitch s1       │
                        ▼                                  │
┌──────────────────────────────────────────────────────────┴──────────────────┐
│                      TIER 3: CORE EXAMINATION & SDN CONTROL                 │
│                                                                             │
│   [TCP Examination Daemon]                  [SDN Controller (OF 1.3)]       │
│     - Authoritative countdown timer           - Port stats polling (18)     │
│     - SQLite WAL database persistence         - 70% congestion trigger      │
│     - Evaluation & scoring engine             - Dynamic HTB Queue 1 rules   │
│     - Length-prefixed JSON framing            - Linux HTB Queue 0 revert    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Responsibilities

| Component | Technology | Responsibility |
|---|---|---|
| **TCP Exam Server** | Python 3 `socket`, `threading` | Authoritative source of truth for timer, scoring, sessions, and SQLite persistence. |
| **FastAPI Gateway** | FastAPI, Uvicorn, WebSockets | Bridges stateless browser HTTP/WS requests to stateful TCP socket streams without compromising exam authority. |
| **TCP Exam Adapter** | `app/protocol.py`, `api/tcp_adapter.py` | Holds open long-lived TCP connection per student session, sends length-prefixed JSON frames, records RTT latencies. |
| **Session Store** | Python `threading.RLock`, UUID4 | Maintains mapping between `gateway_session_id` and the socket adapter; auto-evicts stale sessions (>2h). |
| **SDN Controller** | Python 3 OpenFlow 1.3 | Manages Open vSwitch s1, polls port metrics, dynamically installs Priority 1000 flows assigning TCP 5000 to Queue 1 on congestion. |
| **Telemetry Store** | File IPC & memory snapshot | Provides non-blocking access to controller telemetry with automatic staleness (>10s) detection. |
| **React Frontend** | React 18, Vite, Recharts, Tailwind | Student exam interface with real-time countdown, Admin results oversight, and interactive NOC dashboard. |

---

## 3. Browser-to-FastAPI-to-TCP Communication Flow

```
Browser (React)                FastAPI Gateway (:8000)             TCP Server (:5000)
      │                                  │                                  │
      ├── POST /api/exam/auth ──────────>│                                  │
      │   {student_id, student_name}     ├── Open TCP socket ──────────────>│
      │                                  ├── Send AUTH_REQUEST (prefixed) ─>│
      │                                  │<── Recv AUTH_RESPONSE ───────────┤
      │<── {gateway_session_id, ...} ────┤                                  │
      │                                  │                                  │
      ├── GET /api/exam/question ───────>│ (X-Session-ID header)            │
      │                                  ├── Send QUESTION_REQUEST ────────>│
      │                                  │<── Recv QUESTION_DELIVERY ───────┤
      │<── {question_id, options, ...} ──┤                                  │
      │                                  │                                  │
      ├── POST /api/exam/answer ────────>│ (X-Session-ID header)            │
      │   {question_id, selected_option} ├── Send SUBMIT_ANSWER ───────────>│
      │                                  │<── Recv ANSWER_ACK (scoring) ────┤
      │<── {is_correct, points, rem} ────┤                                  │
      │                                  │                                  │
      ├── POST /api/exam/submit ────────>│                                  │
      │                                  ├── Send EXAM_SUBMIT ─────────────>│
      │                                  │<── Recv RESULT_RESPONSE ─────────┤
      │                                  ├── Close & remove socket adapter  │
      │<── {score, total, percentage} ───┤                                  │
```

---

## 4. SDN Telemetry & IPC Architecture

To allow the SDN controller to run as an independent background daemon (or inside Mininet/Ubuntu) while the FastAPI gateway runs as a web server, telemetry is mediated through a **dual-mode IPC**:

1. **In-Memory Store**: Direct method invocation (`update()`) when running in combined processes.
2. **File-Based Snapshot IPC**: The controller writes `results/sdn_telemetry_snapshot.json` on every stats collection cycle and policy event transition. The gateway inspects file modification times and serves snapshots via `/api/sdn/telemetry` and `/ws/sdn/monitor`.
3. **Staleness Detection**: Snapshots older than 10.0 seconds are automatically flagged with `stale: true`, signaling to the UI that the controller may be paused or stopped.
4. **Offline Resilience**: When the controller has not yet started, the UI displays an honest **Standby / Disconnected** badge rather than fabricating measurements.

---

## 5. Local Windows Development Instructions

### Prerequisites
- Python 3.10+
- Node.js v18+ and npm

### Step-by-Step Launch
Open separate PowerShell windows (or use `scripts\run_prototype_windows.bat` Option 5):

```powershell
# Window 1: Start TCP Examination Server
cd "E:\GitHub Projects\SDN\online-exam-sdn"
python app/server.py --host 0.0.0.0 --port 5000 --duration 300 --questions 5

# Window 2: Start FastAPI Web Gateway
cd "E:\GitHub Projects\SDN\online-exam-sdn"
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Window 3: Start React Frontend
cd "E:\GitHub Projects\SDN\online-exam-sdn\frontend"
npm run dev
```

- **Student Exam Portal**: http://localhost:5173
- **Admin Dashboard**: http://localhost:5173/admin
- **SDN Network NOC**: http://localhost:5173/sdn
- **FastAPI OpenAPI Swagger**: http://localhost:8000/docs

---

## 6. Ubuntu Deployment Instructions

```bash
cd ~/online-exam-sdn

# 1. Install dependencies
bash scripts/setup_ubuntu.sh
pip install -r api/requirements.txt

# 2. Build frontend for production
cd frontend && npm install && npm run build && cd ..

# 3. Start controller
bash scripts/run_controller.sh &

# 4. Start TCP server
bash scripts/run_server.sh &

# 5. Start web gateway
bash scripts/run_gateway.sh &
```

---

## 7. Mininet Network Deployment & Traffic Preservation

### Critical Routing Architecture

```
Host h1 (10.0.0.1)  <─── Open vSwitch s1 (OpenFlow 1.3) ───>  Host h2, h3, h4 (10.0.0.2-4)
Exam Server (:5000)            (Linux HTB Queues)             FastAPI Gateway (:8000)
                                                              Browser UI (:5173)
```

1. **Exam Server Host `h1`**: Executes `python3 app/server.py --host 10.0.0.1 --port 5000`.
2. **Student Hosts `h2`, `h3`, `h4`**: Run student-side FastAPI gateway instances configured with:
   `EXAM_SERVER_HOST=10.0.0.1 EXAM_SERVER_PORT=5000 python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000`
3. **Traffic Path**: The browser communicates with its local gateway on `http://10.0.0.x:8000`. The gateway opens a TCP socket connection across the virtual interface to `10.0.0.1:5000`.
4. **Open vSwitch Classification**: All candidate examination traffic enters switch `s1` with TCP destination port 5000. Under congestion (>70% bottleneck link utilization caused by host `h5`), the controller installs OpenFlow rules directing this traffic into **Queue 1 (7–10 Mbps guaranteed bandwidth)**.

---

## 8. Environment Variables Reference

| Variable | Default | Purpose |
|---|---|---|
| `EXAM_SERVER_HOST` | `127.0.0.1` | IP of authoritative TCP examination server |
| `EXAM_SERVER_PORT` | `5000` | Port of authoritative TCP examination server |
| `GATEWAY_HOST` | `0.0.0.0` | Listen host for FastAPI gateway |
| `GATEWAY_PORT` | `8000` | Listen port for FastAPI gateway |
| `DB_PATH` | `exam_records.db` | SQLite database file path |
| `ADMIN_PASSWORD` | *(None / Required)* | Server-side password required to log into `/admin` |
| `SESSION_SECRET` | *(Random 256-bit)* | Secret key for signing HTTP-only HMAC-SHA256 session cookies |
| `SESSION_COOKIE_SECURE` | `false` | Sets `Secure` flag on session cookie (set true if using HTTPS) |
| `SESSION_MAX_AGE_SEC` | `28800` | Session lifetime in seconds (8 hours) |
| `SDN_ENABLED` | `false` | Enables live SDN controller integration |
| `START_EXAM_SERVER` | `false` | Automatically starts in-process TCP server |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Allowed CORS origins for web requests |
| `VITE_API_URL` | `http://localhost:8000` | Frontend backend API URL |
| `VITE_WS_URL` | `ws://localhost:8000` | Frontend WebSocket endpoint |

---

## 9. Related Documentation

- **[docs/FINAL_DEMO_GUIDE.md](FINAL_DEMO_GUIDE.md)**: 11-step viva and evaluation presentation guide.
- **[docs/MININET_DEPLOYMENT.md](MININET_DEPLOYMENT.md)**: Comprehensive Ubuntu Linux & Mininet setup instructions.
- **[README.md](../README.md)**: Master project documentation and quantitative performance benchmark analysis.
