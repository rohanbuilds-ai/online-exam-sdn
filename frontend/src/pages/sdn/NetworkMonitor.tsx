import React, { useState, useEffect } from "react"
import {
  Activity,
  Cpu,
  Shield,
  Layers,
  Clock,
  RotateCcw,
  BarChart2,
  Wifi,
  WifiOff
} from "lucide-react"
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend
} from "recharts"
import { Card, CardHeader, CardTitle } from "../../components/ui/Card"
import { Button } from "../../components/ui/Button"
import { Badge } from "../../components/ui/Badge"
import { useSdnTelemetry } from "../../hooks/useSdnTelemetry"
import { getSdnHistory } from "../../lib/api"
import { HistoricalResults } from "../../types/sdn"
import { formatPercent, formatDateTime } from "../../lib/utils"

export const NetworkMonitor: React.FC = () => {
  const { telemetry, loading: telemetryLoading, refresh: refreshTelemetry } = useSdnTelemetry()
  const [history, setHistory] = useState<HistoricalResults | null>(null)
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState<string | null>(null)

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const data = await getSdnHistory()
        setHistory(data)
      } catch (err: any) {
        setHistoryError(err.message || "Failed to load historical benchmark results.")
      } finally {
        setHistoryLoading(false)
      }
    }
    loadHistory()
  }, [])

  // Process historical benchmark data for charts
  const latencyChartData = [5, 10, 20].map((clients) => {
    const baseNormal = history?.baseline.find(
      (r) => r.concurrency === clients && r.condition.includes("Normal")
    )?.avg_latency_ms
    const baseCongest = history?.baseline.find(
      (r) => r.concurrency === clients && r.condition.includes("Congested")
    )?.avg_latency_ms
    const dynNormal = history?.dynamic.find(
      (r) => r.concurrency === clients && r.condition.includes("Normal")
    )?.avg_latency_ms
    const dynCongest = history?.dynamic.find(
      (r) => r.concurrency === clients && r.condition.includes("Congested")
    )?.avg_latency_ms

    return {
      clients: `${clients} Students`,
      "Baseline (Normal)": baseNormal ?? null,
      "Baseline (Congested)": baseCongest ?? null,
      "Dynamic SDN (Normal)": dynNormal ?? null,
      "Dynamic SDN (Congested - QoS Active)": dynCongest ?? null,
    }
  })

  const throughputFairnessData = [5, 10, 20].map((clients) => {
    const baseCongest = history?.baseline.find(
      (r) => r.concurrency === clients && r.condition.includes("Congested")
    )
    const dynCongest = history?.dynamic.find(
      (r) => r.concurrency === clients && r.condition.includes("Congested")
    )

    return {
      clients: `${clients} Students`,
      "Baseline (Congested)": baseCongest?.throughput_req_per_sec ?? 0,
      "Dynamic SDN (QoS Active)": dynCongest?.throughput_req_per_sec ?? 0,
    }
  })

  const isLive = telemetry.available && !telemetry.stale
  const isCongested = telemetry.congestion_state === "CONGESTED"

  return (
    <div className="space-y-8">
      {/* Page Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="h-2 w-2 rounded-full bg-indigo-600 animate-ping" />
            <span className="text-xs font-bold text-indigo-700 tracking-wider uppercase">
              Network Operations Center
            </span>
          </div>
          <h2 className="text-2xl font-black text-slate-900 tracking-tight">
            SDN Topology & Traffic Telemetry
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Real-time OpenFlow 1.3 switch telemetry, queue allocations, and empirical Mininet benchmarks.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={refreshTelemetry}>
            <RotateCcw className="h-4 w-4" />
            Refresh Telemetry
          </Button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* SECTION 1: LIVE TELEMETRY & NETWORK TOPOLOGY */}
      {/* ========================================================================= */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-indigo-600" />
            <h3 className="text-lg font-bold text-slate-900">Live Network Telemetry</h3>
          </div>
          <div className="flex items-center gap-2">
            {isLive ? (
              <Badge variant="success" className="gap-1.5 py-1 px-3">
                <Wifi className="h-3.5 w-3.5" />
                Live Telemetry Active
              </Badge>
            ) : (
              <Badge variant="neutral" className="gap-1.5 py-1 px-3">
                <WifiOff className="h-3.5 w-3.5 text-slate-500" />
                Controller Standby / Offline
              </Badge>
            )}
          </div>
        </div>

        {/* Telemetry Standby Alert when Controller is not running */}
        {!isLive && (
          <div className="p-3.5 bg-slate-100 border border-slate-200 rounded-xl text-xs text-slate-700 flex items-start gap-2.5">
            <WifiOff className="h-4 w-4 text-slate-500 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <span className="font-bold text-slate-900">SDN Controller Standby State:</span>
              <p className="text-slate-600">
                The OpenFlow 1.3 controller is not currently active. The diagram below illustrates the architectural Mininet topology. Dynamic queue switching, port bandwidth polling, and event logs will stream automatically when the controller is running in Ubuntu Mininet.
              </p>
            </div>
          </div>
        )}

        {/* Live Topology SVG Map */}
        <Card className="overflow-hidden border-slate-200">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-bold flex items-center justify-between w-full">
              <span>Configured Mininet Topology Layout (10 Mbps Bottleneck Links)</span>
              <span className="text-xs font-mono text-slate-500">OpenFlow 1.3 • Linux HTB QoS</span>
            </CardTitle>
          </CardHeader>

          {/* SVG Diagram */}
          <div className="relative bg-slate-950 p-6 rounded-xl border border-slate-800 text-white overflow-x-auto">
            <svg
              className="w-full min-w-[700px] h-72 select-none"
              viewBox="0 0 800 300"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              {/* Controller Box Top */}
              <g transform="translate(320, 15)">
                <rect
                  width="160"
                  height="50"
                  rx="10"
                  fill={isLive ? "#1E1B4B" : "#1E293B"}
                  stroke={isLive ? "#4F46E5" : "#64748B"}
                  strokeWidth="2"
                />
                <text x="80" y="26" textAnchor="middle" fill="#FFFFFF" fontSize="12" fontWeight="bold">
                  SDN Controller c0
                </text>
                <text x="80" y="40" textAnchor="middle" fill={isLive ? "#818CF8" : "#94A3B8"} fontSize="10" fontFamily="monospace">
                  {isLive ? "127.0.0.1:6653 (Active)" : "127.0.0.1:6653 (Standby)"}
                </text>
              </g>

              {/* Line: Controller to Switch */}
              <line
                x1="400"
                y1="65"
                x2="400"
                y2="120"
                stroke={isLive ? "#6366F1" : "#475569"}
                strokeWidth="2"
                strokeDasharray="4 4"
              />
              <text x="410" y="95" fill={isLive ? "#A5B4FC" : "#64748B"} fontSize="10">
                {isLive ? "OpenFlow 1.3 Control Channel" : "Control Channel (Standby)"}
              </text>

              {/* Open vSwitch s1 in Center */}
              <g transform="translate(320, 120)">
                <rect
                  width="160"
                  height="70"
                  rx="12"
                  fill="#0F172A"
                  stroke={!isLive ? "#64748B" : isCongested ? "#F43F5E" : "#10B981"}
                  strokeWidth="2"
                />
                <text x="80" y="30" textAnchor="middle" fill="#FFFFFF" fontSize="13" fontWeight="bold">
                  Open vSwitch s1
                </text>
                <text x="80" y="47" textAnchor="middle" fill="#94A3B8" fontSize="10" fontFamily="monospace">
                  DPID: 0000000000000001
                </text>
                <text
                  x="80"
                  y="62"
                  textAnchor="middle"
                  fill={!isLive ? "#94A3B8" : isCongested ? "#FDA4AF" : "#6EE7B7"}
                  fontSize="9"
                  fontWeight="bold"
                >
                  {!isLive
                    ? "○ Standby: Default Queue 0"
                    : isCongested
                    ? "★ Dynamic QoS: Queue 1"
                    : "● Standard QoS: Queue 0"}
                </text>
              </g>

              {/* Left Side: Server h1 */}
              <g transform="translate(30, 130)">
                <rect
                  width="140"
                  height="60"
                  rx="10"
                  fill="#064E3B"
                  stroke="#10B981"
                  strokeWidth="2"
                />
                <text x="70" y="27" textAnchor="middle" fill="#FFFFFF" fontSize="12" fontWeight="bold">
                  Exam Server h1
                </text>
                <text x="70" y="43" textAnchor="middle" fill="#6EE7B7" fontSize="10" fontFamily="monospace">
                  10.0.0.1:5000 (TCP)
                </text>
              </g>

              {/* Link: h1 to s1 (Port 1 - Bottleneck) */}
              <line
                x1="170"
                y1="155"
                x2="320"
                y2="155"
                stroke={!isLive ? "#64748B" : isCongested ? "#F43F5E" : "#10B981"}
                strokeWidth={isCongested ? "4" : "2.5"}
              />
              <rect
                x="200"
                y="142"
                width="90"
                height="18"
                rx="4"
                fill="#020617"
                stroke="#334155"
              />
              <text x="245" y="155" textAnchor="middle" fill="#F8FAFC" fontSize="9" fontWeight="bold">
                s1-eth1 (10 Mbps)
              </text>

              {/* Right Side Hosts: Students h2, h3, h4 & Background Traffic h5 */}
              {/* Student h2 */}
              <g transform="translate(630, 80)">
                <rect width="130" height="40" rx="8" fill="#1E293B" stroke="#38BDF8" strokeWidth="1.5" />
                <text x="65" y="20" textAnchor="middle" fill="#FFFFFF" fontSize="11" fontWeight="bold">
                  Student h2
                </text>
                <text x="65" y="33" textAnchor="middle" fill="#7DD3FC" fontSize="9" fontFamily="monospace">
                  10.0.0.2:5000
                </text>
              </g>
              <line x1="480" y1="145" x2="630" y2="100" stroke="#38BDF8" strokeWidth="1.5" />

              {/* Student h3 */}
              <g transform="translate(630, 130)">
                <rect width="130" height="40" rx="8" fill="#1E293B" stroke="#38BDF8" strokeWidth="1.5" />
                <text x="65" y="20" textAnchor="middle" fill="#FFFFFF" fontSize="11" fontWeight="bold">
                  Student h3
                </text>
                <text x="65" y="33" textAnchor="middle" fill="#7DD3FC" fontSize="9" fontFamily="monospace">
                  10.0.0.3:5000
                </text>
              </g>
              <line x1="480" y1="155" x2="630" y2="150" stroke="#38BDF8" strokeWidth="1.5" />

              {/* Student h4 */}
              <g transform="translate(630, 180)">
                <rect width="130" height="40" rx="8" fill="#1E293B" stroke="#38BDF8" strokeWidth="1.5" />
                <text x="65" y="20" textAnchor="middle" fill="#FFFFFF" fontSize="11" fontWeight="bold">
                  Student h4
                </text>
                <text x="65" y="33" textAnchor="middle" fill="#7DD3FC" fontSize="9" fontFamily="monospace">
                  10.0.0.4:5000
                </text>
              </g>
              <line x1="480" y1="165" x2="630" y2="200" stroke="#38BDF8" strokeWidth="1.5" />

              {/* BG Traffic Host h5 */}
              <g transform="translate(630, 235)">
                <rect
                  width="130"
                  height="45"
                  rx="8"
                  fill="#4C0519"
                  stroke="#FB7185"
                  strokeWidth="1.5"
                />
                <text x="65" y="20" textAnchor="middle" fill="#FFFFFF" fontSize="11" fontWeight="bold">
                  ⚡ BG Traffic h5
                </text>
                <text x="65" y="35" textAnchor="middle" fill="#FDA4AF" fontSize="9" fontFamily="monospace">
                  10.0.0.5 (8.5M iperf)
                </text>
              </g>
              <line
                x1="480"
                y1="175"
                x2="630"
                y2="255"
                stroke="#FB7185"
                strokeWidth="2"
                strokeDasharray={isLive && isCongested ? "3 3" : undefined}
              />
            </svg>
          </div>
        </Card>

        {/* Live Controller Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Controller Status */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <Cpu className="h-4 w-4 text-indigo-600" />
                <CardTitle className="text-sm font-bold">Controller Link Status</CardTitle>
              </div>
              <Badge variant={isLive ? "success" : "neutral"}>
                {isLive ? "Online" : "Standby"}
              </Badge>
            </CardHeader>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Connected Switches:</span>
                <span className="font-bold text-slate-900">
                  {isLive ? telemetry.switch_count : "— (Standby)"}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Control Protocol:</span>
                <span className="font-mono font-semibold text-slate-800">OpenFlow 1.3</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-500">Listen Port:</span>
                <span className="font-mono font-semibold text-slate-800">6653 (TCP)</span>
              </div>
            </div>
          </Card>

          {/* Dynamic QoS Policy State */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4 text-emerald-600" />
                <CardTitle className="text-sm font-bold">Congestion & Policy State</CardTitle>
              </div>
              <Badge
                variant={
                  !isLive
                    ? "neutral"
                    : telemetry.congestion_state === "CONGESTED"
                    ? "danger"
                    : "success"
                }
              >
                {!isLive ? "STANDBY" : telemetry.congestion_state}
              </Badge>
            </CardHeader>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Congestion Threshold:</span>
                <span className="font-bold text-slate-900">70.0% link capacity</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Recovery Threshold:</span>
                <span className="font-bold text-slate-900">35.0% link capacity</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-500">Adaptive Policy Active:</span>
                <span
                  className={`font-bold ${
                    !isLive
                      ? "text-slate-500"
                      : telemetry.policy_active
                      ? "text-rose-600"
                      : "text-emerald-600"
                  }`}
                >
                  {!isLive
                    ? "STANDBY (Offline)"
                    : telemetry.policy_active
                    ? "YES — Queue 1 Enforced"
                    : "NO — Best Effort"}
                </span>
              </div>
            </div>
          </Card>

          {/* Linux HTB Queue Allocation */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <Layers className="h-4 w-4 text-teal-600" />
                <CardTitle className="text-sm font-bold">HTB Queue Allocation</CardTitle>
              </div>
              <Badge variant="info">s1-eth1</Badge>
            </CardHeader>
            <div className="space-y-2 text-xs">
              <div
                className={`p-2 rounded-lg border flex items-center justify-between ${
                  !isLive || telemetry.queue_assignment === 0 || !telemetry.policy_active
                    ? "bg-slate-100 border-slate-300 font-bold"
                    : "bg-slate-50/60 border-slate-200 text-slate-500"
                }`}
              >
                <span>Queue 0: Best Effort (1–5 Mbps)</span>
                {(!isLive || !telemetry.policy_active || telemetry.queue_assignment === 0) && (
                  <span className="text-[10px] bg-slate-800 text-white px-1.5 py-0.5 rounded">
                    {isLive ? "Active" : "Default"}
                  </span>
                )}
              </div>
              <div
                className={`p-2 rounded-lg border flex items-center justify-between ${
                  isLive && telemetry.policy_active
                    ? "bg-rose-50 border-rose-300 font-bold text-rose-900"
                    : "bg-slate-50/60 border-slate-200 text-slate-500"
                }`}
              >
                <span>Queue 1: Exam Priority (7–10 Mbps)</span>
                {isLive && telemetry.policy_active && (
                  <span className="text-[10px] bg-rose-600 text-white px-1.5 py-0.5 rounded animate-pulse">
                    High Priority
                  </span>
                )}
              </div>
            </div>
          </Card>
        </div>

        {/* Policy Event Timeline */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-indigo-600" />
              <CardTitle className="text-sm font-bold">SDN Dynamic Policy Decision History</CardTitle>
            </div>
            <span className="text-xs text-slate-500">{telemetry.policy_events?.length ?? 0} Events Logged</span>
          </CardHeader>
          {telemetry.policy_events && telemetry.policy_events.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider border-b border-slate-200">
                  <tr>
                    <th className="py-2 px-3">Time</th>
                    <th className="py-2 px-3">Port</th>
                    <th className="py-2 px-3">Utilization</th>
                    <th className="py-2 px-3">Transition</th>
                    <th className="py-2 px-3">Enforced Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-medium">
                  {telemetry.policy_events.slice(-5).reverse().map((ev, idx) => (
                    <tr key={idx} className="hover:bg-slate-50/60">
                      <td className="py-2 px-3 font-mono text-slate-500">{formatDateTime(ev.timestamp)}</td>
                      <td className="py-2 px-3 font-bold text-slate-800">Port {ev.port_no}</td>
                      <td className="py-2 px-3 font-bold text-slate-900">{formatPercent(ev.utilization_percent)}</td>
                      <td className="py-2 px-3">
                        <Badge variant={ev.new_state === "CONGESTED" ? "danger" : "success"}>
                          {ev.previous_state} → {ev.new_state}
                        </Badge>
                      </td>
                      <td className="py-2 px-3 text-slate-700 truncate max-w-xs">{ev.action}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="py-6 text-center text-xs text-slate-500">
              {isLive
                ? "Network traffic is currently normal (<70% link utilization). No QoS threshold events recorded."
                : "Standby — Policy transition history will record when OpenFlow 1.3 congestion threshold events occur."}
            </div>
          )}
        </Card>
      </div>

      {/* ========================================================================= */}
      {/* SECTION 2: HISTORICAL MININET EXPERIMENT RESULTS */}
      {/* ========================================================================= */}
      <div className="space-y-4 pt-4 border-t-2 border-slate-200">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <BarChart2 className="h-5 w-5 text-indigo-600" />
              <h3 className="text-lg font-bold text-slate-900">
                Empirical Performance Benchmarks (Ubuntu Mininet)
              </h3>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Verified experimental measurements comparing Static SDN against Dynamic OpenFlow 1.3 QoS.
            </p>
          </div>
          <Badge variant="neutral">Verified Linux Dataset</Badge>
        </div>

        {historyLoading ? (
          <div className="py-12 text-center text-xs text-slate-500">
            Loading verified benchmark datasets...
          </div>
        ) : (
          <div className="space-y-6">
            {/* Chart 1: Latency Comparison Chart */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-bold">
                  Average Application Request Latency (ms) across Client Concurrencies
                </CardTitle>
                <span className="text-xs text-slate-500">Lower is better</span>
              </CardHeader>
              <div className="h-72 w-full pt-4">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={latencyChartData} margin={{ top: 10, right: 30, left: 0, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                    <XAxis dataKey="clients" tick={{ fontSize: 12, fill: "#475569" }} />
                    <YAxis tick={{ fontSize: 12, fill: "#475569" }} unit=" ms" />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#FFFFFF",
                        border: "1px solid #CBD5E1",
                        borderRadius: "8px",
                        fontSize: "12px",
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: "12px", paddingTop: "10px" }} />
                    <Line
                      type="monotone"
                      dataKey="Baseline (Normal)"
                      stroke="#94A3B8"
                      strokeWidth={2}
                      dot={{ r: 4 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="Baseline (Congested)"
                      stroke="#F43F5E"
                      strokeWidth={2.5}
                      dot={{ r: 5 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="Dynamic SDN (Normal)"
                      stroke="#6366F1"
                      strokeWidth={2}
                      dot={{ r: 4 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="Dynamic SDN (Congested - QoS Active)"
                      stroke="#10B981"
                      strokeWidth={3}
                      dot={{ r: 5 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>

            {/* Chart 2: Throughput Under 8.5 Mbps UDP Congestion */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-bold">
                  Throughput (req/sec) Under Background Congestion
                </CardTitle>
                <span className="text-xs text-slate-500">Higher is better</span>
              </CardHeader>
              <div className="h-64 w-full pt-4">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={throughputFairnessData} margin={{ top: 10, right: 30, left: 0, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                    <XAxis dataKey="clients" tick={{ fontSize: 12, fill: "#475569" }} />
                    <YAxis tick={{ fontSize: 12, fill: "#475569" }} unit=" rps" />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#FFFFFF",
                        border: "1px solid #CBD5E1",
                        borderRadius: "8px",
                        fontSize: "12px",
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: "12px", paddingTop: "10px" }} />
                    <Bar dataKey="Baseline (Congested)" fill="#FB7185" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Dynamic SDN (QoS Active)" fill="#10B981" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            {/* Benchmark Comparison Table */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-bold">
                  Consolidated Experimental Results Dataset
                </CardTitle>
                <span className="text-xs text-slate-500">results/dynamic_sdn_results.json & baseline_results.json</span>
              </CardHeader>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider border-b border-slate-200">
                    <tr>
                      <th className="py-2.5 px-3">Architecture</th>
                      <th className="py-2.5 px-3">Clients</th>
                      <th className="py-2.5 px-3">Traffic Condition</th>
                      <th className="py-2.5 px-3">Mean Latency</th>
                      <th className="py-2.5 px-3">P95 Latency</th>
                      <th className="py-2.5 px-3">Throughput</th>
                      <th className="py-2.5 px-3">Jain's Index</th>
                      <th className="py-2.5 px-3">Completion</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-medium">
                    {history?.dynamic.map((r, idx) => (
                      <tr key={`dyn-${idx}`} className="hover:bg-slate-50/60">
                        <td className="py-2 px-3 font-semibold text-indigo-700">{r.architecture}</td>
                        <td className="py-2 px-3 font-bold text-slate-900">{r.concurrency}</td>
                        <td className="py-2 px-3">
                          <Badge variant={r.condition.includes("Congested") ? "warning" : "neutral"}>
                            {r.condition}
                          </Badge>
                        </td>
                        <td className="py-2 px-3 font-bold text-slate-900">{r.avg_latency_ms} ms</td>
                        <td className="py-2 px-3 text-slate-600">{r.p95_latency_ms} ms</td>
                        <td className="py-2 px-3 font-semibold text-emerald-700">{r.throughput_req_per_sec} rps</td>
                        <td className="py-2 px-3 font-mono text-slate-800">{r.jains_fairness_index}</td>
                        <td className="py-2 px-3">
                          <Badge variant="success">{r.completion_rate_percent}%</Badge>
                        </td>
                      </tr>
                    ))}
                    {history?.baseline.map((r, idx) => (
                      <tr key={`base-${idx}`} className="hover:bg-slate-50/60 opacity-80">
                        <td className="py-2 px-3 text-slate-500">{r.architecture}</td>
                        <td className="py-2 px-3 font-bold text-slate-700">{r.concurrency}</td>
                        <td className="py-2 px-3 text-slate-600">{r.condition}</td>
                        <td className="py-2 px-3 text-slate-800">{r.avg_latency_ms} ms</td>
                        <td className="py-2 px-3 text-slate-600">{r.p95_latency_ms} ms</td>
                        <td className="py-2 px-3 text-slate-600">{r.throughput_req_per_sec} rps</td>
                        <td className="py-2 px-3 font-mono text-slate-700">{r.jains_fairness_index}</td>
                        <td className="py-2 px-3">
                          <Badge variant="neutral">{r.completion_rate_percent}%</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}
