# SDN-Based Online Examination Network — Final Demonstration & Presentation Guide

This guide provides an end-to-end, 11-step demonstration script designed for viva defense, engineering evaluations, and project demonstrations.

---

## Demonstration Status Matrix

| Component / Capability | Category | Verification Level | Demonstration Mode |
|---|:---:|:---:|:---:|
| **Framed TCP Protocol** (`app/protocol.py`) | Implemented & Unit-Tested | 5/5 Unit Tests Passing | Live TCP Socket Framing |
| **Authoritative Exam Daemon** (`app/server.py`) | Implemented & Unit-Tested | Concurrency & Timer Tests Passing | Active TCP Process (Port 5000) |
| **SQLite Persistence** (`app/storage.py`) | Implemented & Unit-Tested | Database Unit Tests Passing | Real-time WAL Storage (`exam_records.db`) |
| **FastAPI Web Adapter** (`api/main.py`) | Implemented & Unit-Tested | 10/10 Gateway Tests Passing | REST & WebSocket Server (Port 8000) |
| **React 18 + TS Frontend** (`frontend/`) | Implemented & Build-Tested | Production Build Passing (`dist/`) | Browser UI (Port 5173 / 8000) |
| **Admin Session Security** (`api/auth.py`) | Implemented & Unit-Tested | Login/Logout/401/Cookie Tests Passing | HTTP-only Cookie Authentication |
| **Pure Python OF 1.3 Controller** (`sdn/controller.py`) | Implemented & Unit-Tested | 5/5 Controller Tests Passing | Tested on Windows + Linux |
| **Historical Performance Dashboard** | Implemented & Verified | Real JSON Data Loaded | Recharts & Dataset Table |
| **Mininet Host Gateway Route (h2 → OVS → h1)** | Packaging Complete | Documented & Packaged | **Pending Live Ubuntu Mininet Verification** |
| **Live Controller Handshake in Topology** | Implementation Ready | Unit-Tested with Mock Switch | **Pending Live Ubuntu Mininet Verification** |
| **Kernel Linux HTB Queue Prioritization** | Scripts Configured | Validated in Baseline Runs | **Pending Live Ubuntu Mininet Verification** |
| **Dynamic Queue 1 Switching Under Live Flood** | Rule Logic Tested | OpenFlow Flow-Mod Tested | **Pending Live Ubuntu Mininet Verification** |

---

## 11-Step Demonstration Script

### Step 1: Introduce the Examination Problem
**What to Explain:**
- Standard online university exams are highly vulnerable to campus network congestion.
- When background bulk transfers (video streaming, software updates, or DoS attacks) flood shared bottleneck links, buffers fill up (bufferbloat).
- Student TCP socket connections suffer packet drops and multi-second latency spikes, resulting in exam disconnections and lost answers.
- **The Solution**: An SDN-controlled network where the OpenFlow controller monitors port utilization in real time and automatically isolates mission-critical examination TCP traffic into a prioritized Quality of Service (QoS) queue.

---

### Step 2: Launch the Prototype on Windows
**Action:**
Open command prompt and run the one-click menu launcher:
```cmd
scripts\run_prototype_windows.bat
```
Select **Option [5]** (*Launch ALL 3 Web Components*).
**What Happens:**
- Three dedicated console windows spawn:
  1. `TCP Exam Server (Port 5000)`
  2. `FastAPI Gateway (Port 8000)`
  3. `React Frontend (Port 5173)`
- The prototype opens at `http://localhost:5173`.

---

### Step 3: Demonstrate Student Login & Presets
**Action:**
1. Navigate to the **Student Portal** at `http://localhost:5173`.
2. Point out the connection health pill in the top header (`TCP Server Reachable: 127.0.0.1:5000`).
3. Click one of the quick-fill demo presets (e.g., `STU001 - Alice Smith`).
4. Click **Authenticate & Continue**.
**What to Explain:**
- The frontend sends `POST /api/exam/auth` to FastAPI.
- FastAPI opens a stateful, persistent TCP socket to the examination daemon on port 5000 and sends a binary length-prefixed `AUTH_REQUEST` frame.
- The server initializes an authoritative session in SQLite and assigns a monotonic exam timer.

---

### Step 4: Review Exam Instructions & Begin Examination
**Action:**
1. On the Instructions page, review the server-enforced rules (duration, question count, pass threshold).
2. Click **Start Examination Now**.
**What to Explain:**
- The student portal calls `GET /api/exam/question`.
- The TCP server delivers Question 1 with remaining time.
- The browser interface transitions into the secure examination workspace.

---

### Step 5: Demonstrate Examination Lifecycle, Navigator & Countdown
**Action:**
1. Show the **Question Panel** with multiple-choice options (A, B, C, D).
2. Point out the **Server-Authoritative Countdown Timer** in the top right:
   - Green state during regular time.
   - Transitions to an animated red warning state when `<60s` remain.
3. Show the **Question Navigator (Grid 1–5)**:
   - Blue ring marks the active question.
   - Green fill indicates answered questions.
   - Gray indicates pending questions.
4. Select an answer and click **Confirm & Save Answer**.
   - Show the instant confirmation feedback banner.
   - Question 2 loads automatically.

---

### Step 6: Confirmation Modal & Final Submission
**Action:**
1. Answer the remaining questions or demonstrate the confirmation modal with unanswered questions:
   - Click **Submit Exam & View Result**.
   - A modal appears showing: *"You have answered X of 5 questions. Are you sure you want to finalize?"*
2. Confirm the submission.
**What to Explain:**
- The gateway sends `EXAM_SUBMIT` over the TCP socket.
- The server evaluates the candidate's answers against the question bank, computes the final percentage, updates SQLite status to `COMPLETED`, and returns an authoritative `RESULT_RESPONSE`.

---

### Step 7: Present Instant Official Results
**Action:**
1. Review the **Result Page**:
   - Total score (e.g., `4 / 5`).
   - Percentage badge (`80.0%`).
   - Status badge (`PASSED` or `FAILED`).
   - Breakdown of duration taken and network QoS policy applied.
**What to Explain:**
- Scores and percentages are calculated exclusively on the server — the client has zero influence over scoring logic.

---

### Step 8: Open the Administration Dashboard
**Action:**
1. Click **Admin Dashboard** in the top navigation (`http://localhost:5173/admin`).
2. Show the **Administrator Session Authentication Gate**:
   - If not logged in, demonstrate the secure login gate. Point out that administrative access is strictly protected on the server side against `ADMIN_PASSWORD`.
   - Enter the server administrator credential and sign in.
   - Point out the `Admin Session Active` badge backed by an HMAC-SHA256 signed HTTP-only cookie.
3. Show the **Live Active TCP Student Streams**:
   - If an exam is in progress, the student's active TCP connection is listed with start time and socket state.
4. Show the **Persistent Examination Results Table**:
   - The test result from Alice Smith is permanently archived in SQLite.
   - Demonstrate the search box (type "Alice") and the status filters ("Passed", "Completed").
5. Show the KPI summary cards: Total Completed Exams, Average Score, Highest Score, Active Sessions.
6. Demonstrate **Logout**: Click **Log Out** to clear the session cookie and return to the login gate.

---

### Step 9: Open the SDN Network Operations Center (NOC)
**Action:**
1. Click **SDN Monitor** in the top navigation (`http://localhost:5173/sdn`).
2. Point out the **Honest Telemetry State**:
   - When running on Windows without Mininet, the banner explicitly displays:
     `Controller Standby / Offline: The OpenFlow 1.3 controller is not currently active.`
   - In the SVG topology, switch `s1` and controller `c0` show clean `Standby` badges rather than fake animated traffic.
3. Point out the **Interactive Topology Map**:
   - Controller `c0` on `127.0.0.1:6653`.
   - Open vSwitch `s1` (DPID: `0000000000000001`).
   - Server `h1` on port 1 (`10.0.0.1:5000`).
   - Student hosts `h2`, `h3`, `h4` on ports 2, 3, 4.
   - Background traffic generator `h5` on port 5.

---

### Step 10: Explain Congestion Detection & Dynamic OpenFlow 1.3 QoS
**What to Explain:**
1. **Link Bottleneck**: All traffic to `h1` traverses the 10 Mbps bottleneck link on `s1-eth1` (Port 1).
2. **Monitoring Mechanism**: The Python SDN controller polls `s1` every 1.0 second using OpenFlow 1.3 `OFPMP_PORT_STATS` multipart requests.
3. **Trigger**: When port utilization exceeds **70.0%** (e.g., `88.5%` caused by 8.5 Mbps UDP flood from `h5`), the controller triggers `CONGESTION_DETECTED`.
4. **Action**: The controller pushes an OpenFlow `OFPFC_ADD` rule (`priority=1000`) matching `tcp_dst=5000` with action `OFPAT_SET_QUEUE` 1.
5. **Isolation**: Linux HTB Queue 1 guarantees 7–10 Mbps for exam packets. Best-effort traffic (iperf UDP) remains trapped in Queue 0 (capped at 1–5 Mbps).
6. **Recovery**: When link utilization drops below **35.0%**, the rule is removed (`OFPFC_DELETE`), returning exam traffic to standard Queue 0.

---

### Step 11: Present Empirical Benchmark Comparisons & Ubuntu Plan
**Action:**
Scroll to Section 2 of the SDN dashboard: **Empirical Performance Benchmarks**.
**Point out the verified data recorded in Mininet:**
- **Average Latency**: Reduced from **23.75 ms** (Baseline) to **10.30 ms** (Dynamic SDN) under 10 clients (**-56.6% reduction**), and from **53.81 ms** to **19.00 ms** under 20 clients (**-64.7% reduction**).
- **P95 Latency**: Reduced from **66.79 ms** to **38.84 ms** (**-41.8%**) under 10 clients, and from **139.41 ms** to **90.39 ms** (**-35.2%**) under 20 clients.
- **Throughput**: Increased by **+52.6%** at 10 clients (205.45 → 313.52 req/s) and by **+143.9%** at 20 clients (194.74 → 474.94 req/s).
- **Packet Loss**: Maintained at **0.0%** across both architectures due to reliable TCP socket retransmissions.
- **Jain's Fairness Index**: Consistently high across all runs (0.9243 → 0.9938 at 5 clients; ~0.99 at 10 and 20 clients), ensuring equitable service.

**Conclude with Ubuntu Deployment Readiness:**
- All controller code, Mininet topology scripts, and test suites are packaged and verified.
- The web application (FastAPI + React) is implemented and unit-tested; live validation of the web prototype traversing Mininet hosts and OVS switch is pending the final Ubuntu VM session (see [docs/MININET_DEPLOYMENT.md](MININET_DEPLOYMENT.md)).
