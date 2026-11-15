import React, { useState } from "react"
import { useNavigate } from "react-router-dom"
import { LogIn, User, Award, ShieldAlert } from "lucide-react"
import { Card, CardHeader, CardTitle } from "../../components/ui/Card"
import { Button } from "../../components/ui/Button"
import { Alert } from "../../components/ui/Alert"
import { authStudent } from "../../lib/api"
import { useExam } from "../../context/ExamContext"

export const LoginPage: React.FC = () => {
  const navigate = useNavigate()
  const { setAuthData, resetExam } = useExam()

  const [studentId, setStudentId] = useState("STU_001")
  const [studentName, setStudentName] = useState("Alice Smith")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!studentId.trim() || !studentName.trim()) {
      setError("Please provide both Student ID and Full Name.")
      return
    }

    setLoading(true)
    setError(null)
    resetExam()

    try {
      const response = await authStudent({
        student_id: studentId.trim(),
        student_name: studentName.trim(),
      })
      setAuthData(response)
      navigate("/exam/instructions")
    } catch (err: any) {
      setError(err.message || "Failed to authenticate with TCP Examination Server.")
    } finally {
      setLoading(false)
    }
  }

  const selectPreset = (id: string, name: string) => {
    setStudentId(id)
    setStudentName(name)
    setError(null)
  }

  return (
    <div className="max-w-xl mx-auto py-8">
      <Card className="shadow-lg border-slate-200">
        <CardHeader className="text-center pb-4 border-b-0">
          <div className="mx-auto h-12 w-12 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 mb-3">
            <Award className="h-6 w-6" />
          </div>
          <CardTitle className="text-2xl font-bold text-slate-900">
            Student Examination Login
          </CardTitle>
          <p className="text-sm text-slate-500 mt-1">
            Authenticate to begin your SDN-monitored examination session.
          </p>
        </CardHeader>

        {error && (
          <Alert variant="danger" className="mb-5" title="Authentication Error">
            {error}
          </Alert>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Student Registration ID
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                <User className="h-4 w-4" />
              </span>
              <input
                type="text"
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
                placeholder="e.g. STU_001"
                required
                className="w-full pl-9 pr-3 py-2.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Student Full Name
            </label>
            <input
              type="text"
              value={studentName}
              onChange={(e) => setStudentName(e.target.value)}
              placeholder="e.g. Alice Smith"
              required
              className="w-full px-3 py-2.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition"
            />
          </div>

          {/* Quick Demo Presets */}
          <div className="pt-2">
            <label className="block text-xs font-medium text-slate-500 mb-1.5">
              Quick Demo Identities:
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: "STU_001", name: "Alice Smith" },
                { id: "STU_002", name: "Bob Jones" },
                { id: "STU_003", name: "Charlie Brown" },
              ].map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => selectPreset(p.id, p.name)}
                  className={`px-2.5 py-1.5 text-xs rounded-md border text-left transition ${
                    studentId === p.id
                      ? "bg-indigo-50 border-indigo-300 text-indigo-700 font-medium"
                      : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  <div className="font-semibold">{p.id}</div>
                  <div className="truncate text-[11px] text-slate-500">{p.name}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="pt-4">
            <Button type="submit" size="lg" className="w-full font-semibold" loading={loading}>
              <LogIn className="h-4 w-4" />
              Sign In & Proceed to Examination
            </Button>
          </div>
        </form>

        <div className="mt-6 pt-5 border-t border-slate-100 text-xs text-slate-500 flex items-start gap-2">
          <ShieldAlert className="h-4 w-4 text-slate-400 shrink-0 mt-0.5" />
          <span>
            Sessions are validated by the authoritative TCP exam daemon. Network traffic traverses OpenFlow 1.3 QoS queues on TCP port 5000.
          </span>
        </div>
      </Card>
    </div>
  )
}
