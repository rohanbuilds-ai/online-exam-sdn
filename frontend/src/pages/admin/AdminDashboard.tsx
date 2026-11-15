import React, { useState, useEffect } from "react"
import {
  Users,
  CheckCircle2,
  TrendingUp,
  RotateCcw,
  Search,
  Activity,
  Award,
  Key,
  Filter,
  Lock
} from "lucide-react"
import { Card, CardHeader, CardTitle } from "../../components/ui/Card"
import { Button } from "../../components/ui/Button"
import { Badge } from "../../components/ui/Badge"
import { Spinner } from "../../components/ui/Spinner"
import { Alert } from "../../components/ui/Alert"
import { getAdminStats, getAdminResults, getAdminSessions, getAdminKey, setAdminKey } from "../../lib/api"
import { AdminStats, StudentResultRecord, ActiveSession } from "../../types/exam"
import { formatDateTime, formatPercent } from "../../lib/utils"

export const AdminDashboard: React.FC = () => {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [results, setResults] = useState<StudentResultRecord[]>([])
  const [sessions, setSessions] = useState<ActiveSession[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isAuthError, setIsAuthError] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("ALL")
  const [resultFilter, setResultFilter] = useState<string>("ALL")
  
  // Admin Key management
  const [adminKey, setAdminKeyState] = useState<string>(getAdminKey())
  const [showKeyInput, setShowKeyInput] = useState(false)
  const [keyDraft, setKeyDraft] = useState(getAdminKey())

  const loadData = async () => {
    setError(null)
    setIsAuthError(false)
    try {
      const [statsData, resultsData, sessionsData] = await Promise.all([
        getAdminStats(adminKey),
        getAdminResults(adminKey),
        getAdminSessions(adminKey),
      ])
      setStats(statsData)
      setResults(resultsData)
      setSessions(sessionsData)
    } catch (err: any) {
      const msg = err.message || "Failed to load admin examination records from SQLite database."
      setError(msg)
      if (msg.includes("403") || msg.includes("forbidden") || msg.includes("Administrative access")) {
        setIsAuthError(true)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 10000) // auto-refresh every 10s
    return () => clearInterval(interval)
  }, [adminKey])

  const handleSaveKey = () => {
    setAdminKey(keyDraft.trim())
    setAdminKeyState(keyDraft.trim())
    setShowKeyInput(false)
  }

  const filteredResults = results.filter((r) => {
    const matchesSearch =
      r.student_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (r.name && r.name.toLowerCase().includes(searchQuery.toLowerCase()))
    
    const matchesStatus =
      statusFilter === "ALL" || r.status === statusFilter

    const isPassed = r.percentage >= 50.0
    const matchesResult =
      resultFilter === "ALL" ||
      (resultFilter === "PASSED" && isPassed) ||
      (resultFilter === "FAILED" && !isPassed)

    return matchesSearch && matchesStatus && matchesResult
  })

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <h2 className="text-2xl font-black text-slate-900 tracking-tight">
            Examination Administration Dashboard
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Real-time session oversight, active TCP connections, and persistent SQLite examination records.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Admin Key pill */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 border border-slate-200 rounded-lg text-xs font-mono">
            <Lock className="h-3.5 w-3.5 text-slate-500" />
            <span className="text-slate-600">Key:</span>
            <span className="font-bold text-slate-800">
              {adminKey.length > 8 ? `${adminKey.slice(0, 4)}...${adminKey.slice(-4)}` : "••••••••"}
            </span>
            <button
              onClick={() => {
                setKeyDraft(adminKey)
                setShowKeyInput(!showKeyInput)
              }}
              className="ml-1 text-indigo-600 hover:text-indigo-800 text-[11px] underline font-sans"
            >
              {showKeyInput ? "Cancel" : "Change"}
            </button>
          </div>

          <Button variant="outline" size="sm" onClick={loadData} disabled={loading}>
            <RotateCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh Records
          </Button>
        </div>
      </div>

      {/* Admin Key update inline panel */}
      {showKeyInput && (
        <Card className="bg-slate-50 border-indigo-200">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
            <div className="space-y-0.5">
              <span className="font-bold text-slate-900">Configure Administrator API Key (X-Admin-Key)</span>
              <p className="text-slate-500">
                Matches the server's <code>ADMIN_API_KEY</code> environment variable (Default: <code>sdn-admin-key-2026</code>).
              </p>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={keyDraft}
                onChange={(e) => setKeyDraft(e.target.value)}
                placeholder="Enter admin API key..."
                className="px-3 py-1.5 border border-slate-300 rounded-lg font-mono text-xs w-56 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
              <Button size="sm" variant="primary" onClick={handleSaveKey}>
                Apply Key
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Error alert with recovery */}
      {error && (
        <Alert variant="danger" title={isAuthError ? "Administrative Access Forbidden (403)" : "Administrative Notice"}>
          <div className="space-y-2">
            <p>{error}</p>
            {isAuthError && (
              <p className="text-xs">
                To protect student privacy, administrative records require a valid <code>X-Admin-Key</code>.
                Click <strong>Change</strong> above to provide the correct key.
              </p>
            )}
          </div>
        </Alert>
      )}

      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="flex items-center gap-4">
          <div className="h-12 w-12 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shrink-0">
            <Users className="h-6 w-6" />
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Total Completed Exams
            </div>
            <div className="text-2xl font-black text-slate-900 mt-0.5">
              {stats?.total_completed_exams ?? "0"}
            </div>
            <div className="text-[11px] text-slate-500">Evaluated in SQLite</div>
          </div>
        </Card>

        <Card className="flex items-center gap-4">
          <div className="h-12 w-12 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600 shrink-0">
            <CheckCircle2 className="h-6 w-6" />
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Average Score
            </div>
            <div className="text-2xl font-black text-slate-900 mt-0.5">
              {formatPercent(stats?.average_percentage)}
            </div>
            <div className="text-[11px] text-slate-500">Across all submissions</div>
          </div>
        </Card>

        <Card className="flex items-center gap-4">
          <div className="h-12 w-12 rounded-xl bg-teal-50 border border-teal-100 flex items-center justify-center text-teal-600 shrink-0">
            <TrendingUp className="h-6 w-6" />
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Highest Score
            </div>
            <div className="text-2xl font-black text-slate-900 mt-0.5">
              {formatPercent(stats?.highest_percentage)}
            </div>
            <div className="text-[11px] text-slate-500">Top candidate score</div>
          </div>
        </Card>

        <Card className="flex items-center gap-4">
          <div className="h-12 w-12 rounded-xl bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-600 shrink-0">
            <Activity className="h-6 w-6" />
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Active TCP Sessions
            </div>
            <div className="text-2xl font-black text-amber-600 mt-0.5">
              {sessions.length}
            </div>
            <div className="text-[11px] text-amber-600 font-medium">Live socket connections</div>
          </div>
        </Card>
      </div>

      {/* Active Examination Sessions (Visual Accent: Amber Theme) */}
      <Card className="border-amber-200/80 bg-amber-50/20">
        <CardHeader className="border-b border-amber-100">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-amber-500" />
            <CardTitle className="text-base text-slate-900">Live Active TCP Student Streams</CardTitle>
          </div>
          <Badge variant={sessions.length > 0 ? "warning" : "neutral"}>
            {sessions.length} Active {sessions.length === 1 ? "Session" : "Sessions"}
          </Badge>
        </CardHeader>

        {sessions.length === 0 ? (
          <div className="py-8 text-center text-sm text-slate-500">
            <Activity className="h-8 w-8 text-slate-300 mx-auto mb-2" />
            <p className="font-semibold text-slate-700">No active student sessions currently connected.</p>
            <p className="text-xs text-slate-500 mt-1">
              When candidates authenticate via the student portal, their live TCP socket connections to the exam daemon (port 5000) appear here.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-amber-100/50 text-slate-600 uppercase tracking-wider border-b border-amber-200">
                <tr>
                  <th className="py-2.5 px-3">Gateway Session ID</th>
                  <th className="py-2.5 px-3">Student ID</th>
                  <th className="py-2.5 px-3">Student Name</th>
                  <th className="py-2.5 px-3">Started At</th>
                  <th className="py-2.5 px-3">TCP Connection State</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-amber-100 font-medium">
                {sessions.map((sess) => (
                  <tr key={sess.gateway_session_id} className="hover:bg-amber-100/30">
                    <td className="py-2.5 px-3 font-mono text-slate-600">
                      {sess.gateway_session_id.substring(0, 13)}...
                    </td>
                    <td className="py-2.5 px-3 font-bold text-slate-900">{sess.student_id}</td>
                    <td className="py-2.5 px-3 text-slate-800">{sess.student_name}</td>
                    <td className="py-2.5 px-3 text-slate-500">{formatDateTime(sess.started_at)}</td>
                    <td className="py-2.5 px-3">
                      <Badge variant="warning" className="animate-pulse">Active TCP Stream (Port 5000)</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Persistent Student Results Table */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2">
            <Award className="h-4 w-4 text-indigo-600" />
            <CardTitle className="text-base">Persistent Examination Results</CardTitle>
            <span className="text-xs text-slate-500 font-normal">
              ({filteredResults.length} records)
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Status Filter */}
            <div className="flex items-center gap-1 text-xs text-slate-500">
              <Filter className="h-3.5 w-3.5 text-slate-400" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-2 py-1 text-xs border border-slate-200 rounded-lg bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                <option value="ALL">All Statuses</option>
                <option value="COMPLETED">Completed</option>
                <option value="TIME_EXPIRED">Time Expired</option>
              </select>
            </div>

            {/* Pass/Fail Filter */}
            <select
              value={resultFilter}
              onChange={(e) => setResultFilter(e.target.value)}
              className="px-2 py-1 text-xs border border-slate-200 rounded-lg bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="ALL">All Outcomes</option>
              <option value="PASSED">Passed (≥50%)</option>
              <option value="FAILED">Failed (&lt;50%)</option>
            </select>

            {/* Search Input */}
            <div className="relative w-full sm:w-48">
              <span className="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-slate-400">
                <Search className="h-3.5 w-3.5" />
              </span>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search candidate..."
                className="w-full pl-8 pr-3 py-1 text-xs border border-slate-300 rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
              />
            </div>
          </div>
        </CardHeader>

        {loading ? (
          <div className="py-12 flex flex-col items-center justify-center text-slate-500">
            <Spinner size="md" className="mb-2" />
            <span className="text-xs">Loading records from SQLite...</span>
          </div>
        ) : filteredResults.length === 0 ? (
          <div className="py-10 text-center text-sm text-slate-500">
            <Award className="h-8 w-8 text-slate-300 mx-auto mb-2" />
            <p className="font-semibold text-slate-700">
              {searchQuery || statusFilter !== "ALL" || resultFilter !== "ALL"
                ? "No candidate results matching filter criteria."
                : "No examination results recorded yet in database."}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Completed student examinations evaluated by the TCP daemon will be permanently archived in <code>exam_records.db</code>.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-3">Student ID</th>
                  <th className="py-2.5 px-3">Candidate Name</th>
                  <th className="py-2.5 px-3">Score</th>
                  <th className="py-2.5 px-3">Percentage</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Result</th>
                  <th className="py-2.5 px-3">Completed At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium">
                {filteredResults.map((rec) => {
                  const passed = rec.percentage >= 50.0
                  return (
                    <tr key={rec.session_id} className="hover:bg-slate-50/60">
                      <td className="py-2.5 px-3 font-bold font-mono text-slate-900">
                        {rec.student_id}
                      </td>
                      <td className="py-2.5 px-3 text-slate-800">{rec.name || "—"}</td>
                      <td className="py-2.5 px-3 font-semibold text-slate-700">
                        {rec.score} / {rec.total_points}
                      </td>
                      <td className="py-2.5 px-3 font-bold text-slate-900">
                        {rec.percentage}%
                      </td>
                      <td className="py-2.5 px-3">
                        <Badge
                          variant={
                            rec.status === "COMPLETED"
                              ? "success"
                              : rec.status === "TIME_EXPIRED"
                              ? "warning"
                              : "danger"
                          }
                        >
                          {rec.status}
                        </Badge>
                      </td>
                      <td className="py-2.5 px-3">
                        <Badge variant={passed ? "success" : "danger"}>
                          {passed ? "PASSED" : "FAILED"}
                        </Badge>
                      </td>
                      <td className="py-2.5 px-3 text-slate-500 font-mono">
                        {formatDateTime(rec.completed_at)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
