import React, { useState, useEffect } from "react"
import {
  Users,
  CheckCircle2,
  TrendingUp,
  RotateCcw,
  Search,
  Activity,
  Award,
  Filter,
  Lock,
  LogOut,
  ShieldCheck
} from "lucide-react"
import { Card, CardHeader, CardTitle } from "../../components/ui/Card"
import { Button } from "../../components/ui/Button"
import { Badge } from "../../components/ui/Badge"
import { Spinner } from "../../components/ui/Spinner"
import { Alert } from "../../components/ui/Alert"
import {
  getAdminStats,
  getAdminResults,
  getAdminSessions,
  adminLogin,
  adminLogout,
  checkAdminSession
} from "../../lib/api"
import { AdminStats, StudentResultRecord, ActiveSession } from "../../types/exam"
import { formatDateTime, formatPercent } from "../../lib/utils"

export const AdminDashboard: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null)
  const [passwordInput, setPasswordInput] = useState("")
  const [loginLoading, setLoginLoading] = useState(false)
  const [loginError, setLoginError] = useState<string | null>(null)

  const [stats, setStats] = useState<AdminStats | null>(null)
  const [results, setResults] = useState<StudentResultRecord[]>([])
  const [sessions, setSessions] = useState<ActiveSession[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("ALL")
  const [resultFilter, setResultFilter] = useState<string>("ALL")

  // Check existing session cookie on initial load
  useEffect(() => {
    const verifySession = async () => {
      try {
        const session = await checkAdminSession()
        if (session.authenticated) {
          setIsAuthenticated(true)
          loadData()
        } else {
          setIsAuthenticated(false)
          setLoading(false)
        }
      } catch {
        setIsAuthenticated(false)
        setLoading(false)
      }
    }
    verifySession()
  }, [])

  const loadData = async () => {
    setError(null)
    setLoading(true)
    try {
      const [statsData, resultsData, sessionsData] = await Promise.all([
        getAdminStats(),
        getAdminResults(),
        getAdminSessions(),
      ])
      setStats(statsData)
      setResults(resultsData)
      setSessions(sessionsData)
    } catch (err: any) {
      const msg = err.message || "Failed to load admin examination records from SQLite database."
      setError(msg)
      if (msg.includes("401") || msg.includes("Unauthorized") || msg.includes("session")) {
        setIsAuthenticated(false)
      }
    } finally {
      setLoading(false)
    }
  }

  // Periodic polling when authenticated
  useEffect(() => {
    if (!isAuthenticated) return
    const interval = setInterval(loadData, 10000) // auto-refresh every 10s
    return () => clearInterval(interval)
  }, [isAuthenticated])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!passwordInput.trim()) return

    setLoginLoading(true)
    setLoginError(null)

    try {
      const res = await adminLogin(passwordInput.trim())
      if (res.status === "authenticated") {
        setIsAuthenticated(true)
        setPasswordInput("")
        loadData()
      }
    } catch (err: any) {
      setLoginError(err.message || "Authentication failed. Check your administrative credentials.")
    } finally {
      setLoginLoading(false)
    }
  }

  const handleLogout = async () => {
    try {
      await adminLogout()
    } catch {
      // ignore
    } finally {
      setIsAuthenticated(false)
      setStats(null)
      setResults([])
      setSessions([])
    }
  }

  // 1. Initial Session Checking State
  if (isAuthenticated === null) {
    return (
      <div className="py-24 flex flex-col items-center justify-center text-slate-500">
        <Spinner size="lg" className="mb-3" />
        <span className="text-xs font-medium">Verifying administrator session...</span>
      </div>
    )
  }

  // 2. Unauthenticated Login Gate
  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto py-12">
        <Card className="shadow-lg border-slate-200 overflow-hidden">
          <CardHeader className="bg-slate-50 border-b border-slate-200/80 pb-4">
            <div className="flex items-center gap-2.5">
              <div className="h-9 w-9 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
                <Lock className="h-4 w-4" />
              </div>
              <div>
                <CardTitle className="text-base text-slate-900">Administrator Access</CardTitle>
                <p className="text-xs text-slate-500 mt-0.5">
                  Server-side session authentication required
                </p>
              </div>
            </div>
          </CardHeader>

          <form onSubmit={handleLogin} className="p-6 space-y-4">
            <div className="text-xs text-slate-600 leading-relaxed">
              Examination records and active candidate streams are restricted. Enter the server-side administrator credential (<code>ADMIN_PASSWORD</code>) to issue a secure HTTP-only session.
            </div>

            {loginError && (
              <Alert variant="danger" title="Authentication Failed">
                {loginError}
              </Alert>
            )}

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700">Administrator Password</label>
              <input
                type="password"
                required
                value={passwordInput}
                onChange={(e) => setPasswordInput(e.target.value)}
                placeholder="Enter admin password..."
                className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition font-mono"
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              size="md"
              loading={loginLoading}
              disabled={loginLoading || !passwordInput.trim()}
              className="w-full font-bold shadow-sm"
            >
              Sign In to Administration
            </Button>
          </form>
        </Card>
      </div>
    )
  }

  // 3. Authenticated Dashboard View
  const filteredResults = results.filter((r) => {
    const studentId = r.student_id || ""
    const studentName = r.name || ""
    const query = searchQuery.toLowerCase()
    const matchesSearch =
      studentId.toLowerCase().includes(query) ||
      studentName.toLowerCase().includes(query)

    const matchesStatus =
      statusFilter === "ALL" || r.status === statusFilter

    const percentage = r.percentage ?? 0
    const isPassed = percentage >= 50.0
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
          {/* Admin Session Badge */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 border border-emerald-200 rounded-lg text-xs font-medium text-emerald-800">
            <ShieldCheck className="h-4 w-4 text-emerald-600" />
            <span>Admin Session Active</span>
          </div>

          <Button variant="outline" size="sm" onClick={loadData} disabled={loading}>
            <RotateCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>

          <Button variant="outline" size="sm" onClick={handleLogout}>
            <LogOut className="h-4 w-4 text-slate-600" />
            Log Out
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="danger" title="Administrative Notice">
          <p>{error}</p>
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

      {/* Active Examination Sessions */}
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
                {sessions.map((sess, idx) => {
                  const sessionId = sess.id || sess.gateway_session_id || `session-${idx}`
                  const displayId = sessionId.length > 13 ? `${sessionId.substring(0, 13)}...` : sessionId
                  return (
                    <tr key={sessionId} className="hover:bg-amber-100/30">
                      <td className="py-2.5 px-3 font-mono text-slate-600" title={sessionId}>
                        {displayId}
                      </td>
                      <td className="py-2.5 px-3 font-bold text-slate-900">{sess.student_id || "—"}</td>
                      <td className="py-2.5 px-3 text-slate-800">{sess.student_name || "—"}</td>
                      <td className="py-2.5 px-3 text-slate-500">{sess.started_at ? formatDateTime(sess.started_at) : "—"}</td>
                      <td className="py-2.5 px-3">
                        <Badge variant="warning" className="animate-pulse">Active TCP Stream (Port 5000)</Badge>
                      </td>
                    </tr>
                  )
                })}
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
                {filteredResults.map((rec, idx) => {
                  const percentage = rec.percentage ?? 0
                  const passed = percentage >= 50.0
                  const recKey = rec.session_id || `rec-${idx}`
                  return (
                    <tr key={recKey} className="hover:bg-slate-50/60">
                      <td className="py-2.5 px-3 font-bold font-mono text-slate-900">
                        {rec.student_id || "—"}
                      </td>
                      <td className="py-2.5 px-3 text-slate-800">{rec.name || "—"}</td>
                      <td className="py-2.5 px-3 font-semibold text-slate-700">
                        {rec.score ?? 0} / {rec.total_points ?? 0}
                      </td>
                      <td className="py-2.5 px-3 font-bold text-slate-900">
                        {formatPercent(percentage)}
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
                          {rec.status || "UNKNOWN"}
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
