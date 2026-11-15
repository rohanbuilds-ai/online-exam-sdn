import React from "react"
import { useNavigate } from "react-router-dom"
import { CheckCircle2, XCircle, ArrowRight, RotateCcw, ShieldCheck } from "lucide-react"
import { Card } from "../../components/ui/Card"
import { Button } from "../../components/ui/Button"
import { Progress } from "../../components/ui/Progress"
import { useExam } from "../../context/ExamContext"
import { formatTime } from "../../lib/utils"

export const ResultPage: React.FC = () => {
  const navigate = useNavigate()
  const { examResult, resetExam } = useExam()

  if (!examResult) {
    navigate("/")
    return null
  }

  const isPassed = examResult.passed
  const percentage = examResult.percentage || 0

  const handleReturn = () => {
    resetExam()
    navigate("/")
  }

  return (
    <div className="max-w-xl mx-auto py-8">
      <Card className="shadow-lg border-slate-200 overflow-hidden">
        {/* Status Header Banner */}
        <div
          className={`p-6 text-center text-white ${
            isPassed ? "bg-gradient-to-br from-emerald-600 to-teal-700" : "bg-gradient-to-br from-rose-600 to-red-700"
          }`}
        >
          <div className="mx-auto h-16 w-16 rounded-2xl bg-white/10 backdrop-blur-xs flex items-center justify-center mb-3">
            {isPassed ? (
              <CheckCircle2 className="h-10 w-10 text-white" />
            ) : (
              <XCircle className="h-10 w-10 text-white" />
            )}
          </div>
          <h2 className="text-2xl font-black tracking-tight">
            {isPassed ? "Examination Passed!" : "Examination Not Passed"}
          </h2>
          <p className="text-white/80 text-sm mt-1">
            Status: {examResult.reason || "COMPLETED"} • Evaluated by Server
          </p>
        </div>

        <div className="p-6 space-y-6">
          {/* Score highlight */}
          <div className="text-center bg-slate-50 border border-slate-200/80 rounded-2xl p-5">
            <span className="text-xs font-bold uppercase tracking-widest text-slate-500">
              Final Authoritative Score
            </span>
            <div className="text-4xl font-black text-slate-900 mt-1 mb-2">
              {examResult.score} / {examResult.total_points}
            </div>
            <div className="max-w-xs mx-auto space-y-1.5">
              <Progress
                value={percentage}
                color={isPassed ? "emerald" : "rose"}
                className="h-3"
              />
              <div className="flex justify-between text-xs font-bold text-slate-600 px-0.5">
                <span>Score: {percentage}%</span>
                <span>Pass Requirement: 50%</span>
              </div>
            </div>
          </div>

          {/* Candidate & Session Details */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="bg-white p-3 rounded-xl border border-slate-200">
              <div className="text-slate-500 font-medium">Candidate Name</div>
              <div className="text-sm font-bold text-slate-900 mt-0.5">{examResult.student_name}</div>
              <div className="font-mono text-slate-500 text-[11px]">{examResult.student_id}</div>
            </div>
            <div className="bg-white p-3 rounded-xl border border-slate-200">
              <div className="text-slate-500 font-medium">Duration Taken</div>
              <div className="text-sm font-bold text-slate-900 mt-0.5">
                {formatTime(examResult.duration_taken_sec || 0)}
              </div>
              <div className="text-slate-500 text-[11px]">Server timer accurate</div>
            </div>
            <div className="bg-white p-3 rounded-xl border border-slate-200">
              <div className="text-slate-500 font-medium">Questions Answered</div>
              <div className="text-sm font-bold text-slate-900 mt-0.5">
                {examResult.questions_answered} of {examResult.total_questions}
              </div>
            </div>
            <div className="bg-white p-3 rounded-xl border border-slate-200">
              <div className="text-slate-500 font-medium">Network QoS Policy</div>
              <div className="text-sm font-bold text-indigo-700 mt-0.5 flex items-center gap-1">
                <ShieldCheck className="h-3.5 w-3.5 text-indigo-600" />
                OpenFlow 1.3
              </div>
              <div className="text-slate-500 text-[11px]">Queue 1 Prioritization</div>
            </div>
          </div>

          <div className="pt-2 flex flex-col sm:flex-row gap-3">
            <Button
              variant="outline"
              size="md"
              className="flex-1 font-semibold"
              onClick={() => navigate("/admin")}
            >
              View Admin Results Table
              <ArrowRight className="h-4 w-4" />
            </Button>
            <Button
              variant="primary"
              size="md"
              className="flex-1 font-semibold"
              onClick={handleReturn}
            >
              <RotateCcw className="h-4 w-4" />
              Take Another Exam
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}
