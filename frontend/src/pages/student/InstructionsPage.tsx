import React from "react"
import { useNavigate } from "react-router-dom"
import { Clock, HelpCircle, ArrowRight, ArrowLeft, Shield } from "lucide-react"
import { Card, CardHeader, CardTitle } from "../../components/ui/Card"
import { Button } from "../../components/ui/Button"
import { Badge } from "../../components/ui/Badge"
import { useExam } from "../../context/ExamContext"
import { formatTime } from "../../lib/utils"

export const InstructionsPage: React.FC = () => {
  const navigate = useNavigate()
  const { authData } = useExam()

  if (!authData) {
    navigate("/")
    return null
  }

  const durationSec = authData.exam_duration_sec || 300
  const totalQuestions = authData.total_questions || 5

  const rules = [
    {
      title: "Authoritative Countdown Timer",
      desc: "The examination timer runs authoritatively on the server. If the timer reaches zero, all submitted answers will be automatically finalized and graded.",
    },
    {
      title: "Multiple Choice Questions (MCQ)",
      desc: "Each question contains four options with exactly one correct answer. Points are awarded upon confirmation.",
    },
    {
      title: "Navigation & Question Flow",
      desc: "You can navigate between questions using the Question Navigator panel or Previous/Next buttons.",
    },
    {
      title: "Adaptive SDN Network Protection",
      desc: "During periods of network congestion, the SDN controller will automatically prioritize your exam TCP socket stream into guaranteed Linux HTB Queue 1.",
    },
    {
      title: "Final Submission",
      desc: "Once you submit your examination, you will immediately receive your final score, pass/fail status, and percentage breakdown.",
    },
  ]

  return (
    <div className="max-w-2xl mx-auto py-6">
      <Card className="shadow-md">
        <CardHeader>
          <div>
            <Badge variant="info" className="mb-2">Session Verified</Badge>
            <CardTitle className="text-xl">Examination Instructions & Regulations</CardTitle>
          </div>
          <div className="flex items-center gap-3 text-right">
            <div>
              <div className="text-xs text-slate-500 font-medium">Candidate</div>
              <div className="text-sm font-bold text-slate-900">{authData.student_name}</div>
              <div className="text-xs font-mono text-slate-500">{authData.student_id}</div>
            </div>
          </div>
        </CardHeader>

        {/* Quick parameters */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 my-4 p-4 rounded-xl bg-slate-50 border border-slate-200">
          <div className="flex items-center gap-2.5">
            <Clock className="h-5 w-5 text-indigo-600" />
            <div>
              <div className="text-xs text-slate-500">Allotted Time</div>
              <div className="text-sm font-bold text-slate-800">{formatTime(durationSec)} ({Math.round(durationSec / 60)} mins)</div>
            </div>
          </div>
          <div className="flex items-center gap-2.5">
            <HelpCircle className="h-5 w-5 text-indigo-600" />
            <div>
              <div className="text-xs text-slate-500">Total Questions</div>
              <div className="text-sm font-bold text-slate-800">{totalQuestions} Questions</div>
            </div>
          </div>
          <div className="flex items-center gap-2.5">
            <Shield className="h-5 w-5 text-indigo-600" />
            <div>
              <div className="text-xs text-slate-500">QoS Priority</div>
              <div className="text-sm font-bold text-emerald-600">Dynamic SDN Active</div>
            </div>
          </div>
        </div>

        {/* Rules List */}
        <div className="space-y-3 my-5">
          <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
            Important Guidelines
          </h4>
          <div className="space-y-2.5">
            {rules.map((rule, idx) => (
              <div key={idx} className="flex items-start gap-3 p-3 rounded-lg border border-slate-100 bg-white">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-700">
                  {idx + 1}
                </span>
                <div>
                  <h5 className="text-sm font-semibold text-slate-900 leading-tight">{rule.title}</h5>
                  <p className="text-xs text-slate-600 mt-1 leading-relaxed">{rule.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="pt-4 border-t border-slate-100 flex items-center justify-between gap-3">
          <Button variant="outline" onClick={() => navigate("/")}>
            <ArrowLeft className="h-4 w-4" />
            Sign Out
          </Button>
          <Button size="lg" onClick={() => navigate("/exam")} className="font-semibold px-6">
            Start Examination Now
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </Card>
    </div>
  )
}
