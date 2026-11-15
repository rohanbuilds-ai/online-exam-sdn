import React, { useState, useEffect } from "react"
import {
  Users,
  CheckCircle2,
  TrendingUp,
  RotateCcw,
  Search,
  Activity,
  Award
} from "lucide-react"
import { Card, CardHeader, CardTitle } from "../../components/ui/Card"
import { Button } from "../../components/ui/Button"
import { Badge } from "../../components/ui/Badge"
import { Spinner } from "../../components/ui/Spinner"
import { Alert } from "../../components/ui/Alert"
import { getAdminStats, getAdminResults, getAdminSessions } from "../../lib/api"
import { AdminStats, StudentResultRecord, ActiveSession } from "../../types/exam"
import { formatDateTime, formatPercent } from "../../lib/utils"

export const AdminDashboard: React.FC = () => {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [results, setResults] = useState<StudentResultRecord[]>([])
  const [sessions, setSessions] = useState<ActiveSession[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState("")

  const loadData = async () => {
    setError(null)
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
      setError(err.message || "Failed to load admin examination records from SQLite database.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 10000) // auto-refresh every 10s
    return () => clearInterval(interval)
  }, [])

  const filteredResults = results.filter(
    (r) =>
      r.student_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (r.name && r.name.toLowerCase().includes(searchQuery.toLowerCase()))
  )

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <h2 className="text-2xl font-black text-slate-900 tracking-tight">
            Examination Administration Dashboard
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Real-time session oversight and persistent SQLite examination results.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={loadData} disabled={loading}>
            <RotateCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh Records
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="danger" title="Administrative Error">
          {error}
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
          </div>
        </Card>
      </div>

      {/* Active Examination Sessions */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-amber-500" />
            <CardTitle className="text-base">Live Active Student Sessions</CardTitle>
          </div>
          <Badge variant={sessions.length > 0 ? "warning" : "neutral"}>
            {sessions.length} Active {sessions.length === 1 ? "Session" : "Sessions"}
          </Badge>
        </CardHeader>

        {sessions.length === 0 ? (
          <div className="py-6 text-center text-sm text-slate-500">
            No student sessions currently active. Students logging in via the portal will appear here in real time.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-3">Gateway Session ID</th>
                  <th className="py-2.5 px-3">Student ID</th>
                  <th className="py-2.5 px-3">Student Name</th>
                  <th className="py-2.5 px-3">Started At</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium">
                {sessions.map((sess) => (
                  <tr key={sess.gateway_session_id} className="hover:bg-slate-50/60">
                    <td className="py-2.5 px-3 font-mono text-slate-600">
                      {sess.gateway_session_id.substring(0, 13)}...
                    </td>
                    <td className="py-2.5 px-3 font-bold text-slate-900">{sess.student_id}</td>
                    <td className="py-2.5 px-3 text-slate-800">{sess.student_name}</td>
                    <td className="py-2.5 px-3 text-slate-500">{formatDateTime(sess.started_at)}</td>
                    <td className="py-2.5 px-3">
                      <Badge variant="warning" className="animate-pulse">Active TCP Stream</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Student Results Table */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Award className="h-4 w-4 text-indigo-600" />
            <CardTitle className="text-base">Persistent Examination Results</CardTitle>
          </div>
          <div className="relative w-full sm:w-64">
            <span className="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-slate-400">
              <Search className="h-3.5 w-3.5" />
            </span>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search candidate..."
              className="w-full pl-8 pr-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
            />
          </div>
        </CardHeader>

        {loading ? (
          <div className="py-12 flex flex-col items-center justify-center text-slate-500">
            <Spinner size="md" className="mb-2" />
            <span className="text-xs">Loading records from SQLite...</span>
          </div>
        ) : filteredResults.length === 0 ? (
          <div className="py-8 text-center text-sm text-slate-500">
            {searchQuery ? "No candidate results matching search query." : "No examination results recorded yet in database."}
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
