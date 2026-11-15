import React, { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import {
  Clock,
  CheckCircle,
  HelpCircle,
  Send,
  AlertTriangle,
  Check
} from "lucide-react"
import { Card, CardHeader, CardTitle } from "../../components/ui/Card"
import { Button } from "../../components/ui/Button"
import { Alert } from "../../components/ui/Alert"
import { Spinner } from "../../components/ui/Spinner"
import { useExam } from "../../context/ExamContext"
import { useTimer } from "../../hooks/useTimer"
import { getQuestion, submitAnswer, submitExam, pingExam } from "../../lib/api"
import { formatTime } from "../../lib/utils"
import { Question } from "../../types/exam"

export const ExamPage: React.FC = () => {
  const navigate = useNavigate()
  const { authData, setExamResult } = useExam()

  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null)
  const [selectedOption, setSelectedOption] = useState<number | null>(null)
  const [answeredMap, setAnsweredMap] = useState<Record<number, number>>({}) // question_id -> selected_option
  const [cachedQuestions, setCachedQuestions] = useState<Record<number, Question>>({}) // question_index (1-based) -> Question
  const [loading, setLoading] = useState(true)
  const [submittingAnswer, setSubmittingAnswer] = useState(false)
  const [submittingExam, setSubmittingExam] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showConfirmModal, setShowConfirmModal] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)

  // Redirect if not authenticated
  useEffect(() => {
    if (!authData) {
      navigate("/")
    }
  }, [authData, navigate])

  const totalQuestions = authData?.total_questions || 5
  const initialDuration = authData?.exam_duration_sec || 300

  // Server-authoritative timer hook
  const { remainingSeconds, isWarning, syncWithServer } = useTimer(
    initialDuration,
    () => handleAutoExpire()
  )

  // Fetch first question on mount
  useEffect(() => {
    if (!authData?.gateway_session_id) return
    loadCurrentQuestion()
  }, [authData])

  // Periodic timer sync with server
  useEffect(() => {
    if (!authData?.gateway_session_id) return
    const syncInterval = setInterval(async () => {
      try {
        const ping = await pingExam(authData.gateway_session_id)
        if (ping.remaining_seconds !== null && ping.remaining_seconds > 0) {
          syncWithServer(ping.remaining_seconds)
        }
      } catch {
        // ping error handled gracefully
      }
    }, 15000)

    return () => clearInterval(syncInterval)
  }, [authData, syncWithServer])

  const loadCurrentQuestion = async () => {
    if (!authData?.gateway_session_id) return
    setLoading(true)
    setError(null)
    setFeedback(null)

    try {
      const q = await getQuestion(authData.gateway_session_id)
      setCurrentQuestion(q)
      setCachedQuestions((prev) => ({ ...prev, [q.number]: q }))
      if (q.remaining_seconds > 0) {
        syncWithServer(q.remaining_seconds)
      }
      // Check if already answered
      setSelectedOption(answeredMap[q.question_id] || null)
    } catch (err: any) {
      if (err.message && err.message.includes("ended")) {
        handleFinalSubmit()
      } else {
        setError(err.message || "Failed to load question from server.")
      }
    } finally {
      setLoading(false)
    }
  }

  const handleSelectOption = async (optionIndex: number) => {
    setSelectedOption(optionIndex)
  }

  const handleConfirmAnswer = async () => {
    if (!currentQuestion || selectedOption === null || !authData?.gateway_session_id) return

    setSubmittingAnswer(true)
    setError(null)

    try {
      const ack = await submitAnswer(authData.gateway_session_id, {
        question_id: currentQuestion.question_id,
        selected_option: selectedOption,
      })

      // Record answer locally by ID and Number
      setAnsweredMap((prev) => ({
        ...prev,
        [currentQuestion.question_id]: selectedOption,
        [currentQuestion.number]: selectedOption,
      }))

      if (ack.remaining_seconds !== undefined && ack.remaining_seconds > 0) {
        syncWithServer(ack.remaining_seconds)
      }

      setFeedback(ack.explanation || (ack.is_correct ? "Answer confirmed!" : "Answer recorded."))

      // If there are more questions, load next question after short delay
      if (currentQuestion.number < totalQuestions) {
        setTimeout(() => {
          loadCurrentQuestion()
        }, 500)
      }
    } catch (err: any) {
      setError(err.message || "Failed to submit answer to server.")
    } finally {
      setSubmittingAnswer(false)
    }
  }

  const handleAutoExpire = async () => {
    console.warn("Server timer expired. Finalizing exam...")
    handleFinalSubmit("TIME_EXPIRED")
  }

  const handleFinalSubmit = async (reasonOverride?: string) => {
    if (!authData?.gateway_session_id) return
    setSubmittingExam(true)

    try {
      const result = await submitExam(authData.gateway_session_id)
      if (reasonOverride) {
        result.reason = reasonOverride
      }
      setExamResult(result)
      navigate("/exam/result")
    } catch (err: any) {
      setError(err.message || "Failed to finalize exam.")
    } finally {
      setSubmittingExam(false)
      setShowConfirmModal(false)
    }
  }

  const answeredCount = Object.keys(answeredMap).length

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      {/* Top Banner: Student Info & Timer */}
      <div className="bg-white rounded-xl border border-slate-200 px-5 py-3 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 font-bold text-sm">
            {authData?.student_name?.charAt(0) || "S"}
          </div>
          <div>
            <div className="text-sm font-bold text-slate-900 leading-tight">
              {authData?.student_name}
            </div>
            <div className="text-xs text-slate-500 font-mono">
              ID: {authData?.student_id} • Online Examination
            </div>
          </div>
        </div>

        {/* Server Authoritative Timer */}
        <div
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg border font-mono font-bold transition-all ${
            isWarning
              ? "bg-rose-50 border-rose-300 text-rose-700 animate-pulse shadow-sm shadow-rose-100"
              : "bg-slate-50 border-slate-200 text-slate-700"
          }`}
        >
          <Clock className={`h-4 w-4 ${isWarning ? "text-rose-600" : "text-slate-500"}`} />
          <span className="text-sm tracking-wide">
            {formatTime(remainingSeconds)}
          </span>
          {isWarning && (
            <span className="text-[10px] uppercase font-sans font-extrabold bg-rose-600 text-white px-1.5 py-0.5 rounded">
              Final Minute
            </span>
          )}
        </div>
      </div>

      {error && (
        <Alert variant="danger" title="Examination System Notice">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <span className="text-xs">{error}</span>
            <div className="flex items-center gap-2 shrink-0">
              <Button size="sm" variant="outline" onClick={loadCurrentQuestion}>
                Retry Question
              </Button>
              <Button size="sm" variant="danger" onClick={() => handleFinalSubmit("COMPLETED")}>
                Retry Submit
              </Button>
            </div>
          </div>
        </Alert>
      )}

      {/* Main Examination Layout: 2 Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Column (8 cols): Question & Options */}
        <div className="lg:col-span-8">
          <Card className="min-h-[480px] flex flex-col justify-between shadow-sm">
            {loading ? (
              <div className="flex-1 flex flex-col items-center justify-center py-20 text-slate-500">
                <Spinner size="lg" className="mb-3" />
                <p className="text-sm font-medium">Retrieving verified question from server...</p>
              </div>
            ) : currentQuestion ? (
              <div className="space-y-6 flex-1 flex flex-col justify-between">
                <div>
                  {/* Question Header */}
                  <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 px-2.5 py-0.5 rounded-full">
                        Question {currentQuestion.number} of {totalQuestions}
                      </span>
                      <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                        {currentQuestion.category}
                      </span>
                    </div>
                    <span className="text-xs font-semibold text-slate-600">
                      {currentQuestion.points} {currentQuestion.points === 1 ? "Point" : "Points"}
                    </span>
                  </div>

                  {/* Question Text */}
                  <h3 className="text-base sm:text-lg font-semibold text-slate-900 leading-snug mb-5">
                    {currentQuestion.question}
                  </h3>

                  {/* Options List */}
                  <div className="space-y-2.5">
                    {currentQuestion.options.map((optText, idx) => {
                      const optionNum = idx + 1
                      const isSelected = selectedOption === optionNum
                      const optionLetter = String.fromCharCode(65 + idx) // A, B, C, D

                      return (
                        <div
                          key={optionNum}
                          onClick={() => handleSelectOption(optionNum)}
                          className={`flex items-start gap-3 p-3.5 rounded-xl border text-sm cursor-pointer transition-all ${
                            isSelected
                              ? "bg-indigo-50/80 border-indigo-400 text-indigo-950 ring-1 ring-indigo-400 shadow-xs"
                              : "bg-white border-slate-200 text-slate-700 hover:bg-slate-50 hover:border-slate-300"
                          }`}
                        >
                          <span
                            className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-xs font-bold transition ${
                              isSelected
                                ? "bg-indigo-600 text-white"
                                : "bg-slate-100 text-slate-600"
                            }`}
                          >
                            {optionLetter}
                          </span>
                          <span className="pt-0.5 leading-relaxed font-medium">
                            {optText}
                          </span>
                        </div>
                      )
                    })}
                  </div>

                  {feedback && (
                    <div className="mt-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
                      <CheckCircle className="h-4 w-4 shrink-0 text-emerald-600" />
                      <span>{feedback}</span>
                    </div>
                  )}
                </div>

                {/* Bottom Action Controls */}
                <div className="pt-5 border-t border-slate-100 flex items-center justify-between gap-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={loadCurrentQuestion}
                    disabled={loading || submittingAnswer}
                  >
                    Refresh Question
                  </Button>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="primary"
                      onClick={handleConfirmAnswer}
                      loading={submittingAnswer}
                      disabled={selectedOption === null || loading}
                      className="font-semibold"
                    >
                      <Check className="h-4 w-4" />
                      Confirm & Save Answer
                    </Button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-16 text-slate-500">
                <HelpCircle className="h-10 w-10 mx-auto text-slate-300 mb-3" />
                <p className="text-sm">No active question found.</p>
              </div>
            )}
          </Card>
        </div>

        {/* Right Column (4 cols): Question Navigation & Submission */}
        <div className="lg:col-span-4 space-y-4">
          {/* Question Navigator */}
          <Card className="shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-bold flex items-center justify-between w-full">
                <span>Question Navigator</span>
                <span className="text-xs font-normal text-slate-500">
                  {answeredCount}/{totalQuestions} Answered
                </span>
              </CardTitle>
            </CardHeader>

            <div className="grid grid-cols-5 gap-2 my-2">
              {Array.from({ length: totalQuestions }, (_, i) => i + 1).map((num) => {
                const isCurrent = currentQuestion?.number === num
                const isAnswered = answeredMap[num] !== undefined || (cachedQuestions[num] && answeredMap[cachedQuestions[num].question_id] !== undefined)
                const isAccessible = cachedQuestions[num] !== undefined || isCurrent

                return (
                  <button
                    key={num}
                    type="button"
                    disabled={!isAccessible}
                    onClick={() => {
                      if (cachedQuestions[num]) {
                        setCurrentQuestion(cachedQuestions[num])
                        setSelectedOption(answeredMap[cachedQuestions[num].question_id] ?? answeredMap[num] ?? null)
                      }
                    }}
                    title={
                      isCurrent
                        ? `Question ${num} (Currently Active)`
                        : isAnswered
                        ? `Question ${num} (Answered)`
                        : isAccessible
                        ? `Question ${num} (Pending Answer)`
                        : `Question ${num} (Upcoming - Answer current question)`
                    }
                    className={`h-9 rounded-lg font-bold text-xs flex items-center justify-center transition-all ${
                      isCurrent
                        ? "bg-indigo-600 text-white ring-2 ring-indigo-400 ring-offset-1 shadow-xs"
                        : isAnswered
                        ? "bg-emerald-100 border border-emerald-300 text-emerald-800 hover:bg-emerald-200"
                        : isAccessible
                        ? "bg-slate-100 border border-slate-300 text-slate-700 hover:bg-slate-200"
                        : "bg-slate-50 border border-slate-200 text-slate-400 cursor-not-allowed opacity-60"
                    }`}
                  >
                    {num}
                  </button>
                )
              })}
            </div>

            {/* Legend */}
            <div className="mt-4 pt-3 border-t border-slate-100 grid grid-cols-3 gap-1 text-[11px] text-slate-500">
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-indigo-600" />
                <span>Current</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
                <span>Answered</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-slate-300" />
                <span>Pending</span>
              </div>
            </div>
          </Card>

          {/* Exam Final Submission Card */}
          <Card className="shadow-sm border-indigo-100 bg-indigo-50/40">
            <div className="space-y-3">
              <div>
                <h4 className="text-sm font-bold text-slate-900">Finish Examination</h4>
                <p className="text-xs text-slate-600 mt-0.5">
                  Ready to submit all responses for authoritative evaluation?
                </p>
              </div>

              <div className="text-xs text-slate-500 bg-white p-2.5 rounded-lg border border-indigo-100 space-y-1">
                <div className="flex justify-between">
                  <span>Questions completed:</span>
                  <span className="font-semibold text-slate-800">{answeredCount} of {totalQuestions}</span>
                </div>
                <div className="flex justify-between">
                  <span>Unanswered remaining:</span>
                  <span className="font-semibold text-slate-800">{Math.max(0, totalQuestions - answeredCount)}</span>
                </div>
              </div>

              <Button
                variant="primary"
                size="md"
                className="w-full font-bold shadow-sm"
                onClick={() => setShowConfirmModal(true)}
                disabled={submittingExam}
              >
                <Send className="h-4 w-4" />
                Submit Exam & View Result
              </Button>
            </div>
          </Card>
        </div>
      </div>

      {/* Confirmation Modal */}
      {showConfirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <Card className="max-w-md w-full shadow-2xl border-slate-300 animate-in fade-in zoom-in-95 duration-150">
            <CardHeader className="border-b-0 pb-2">
              <div className="flex items-center gap-2 text-amber-600">
                <AlertTriangle className="h-5 w-5" />
                <CardTitle className="text-lg">Confirm Exam Submission</CardTitle>
              </div>
            </CardHeader>
            <div className="space-y-3 py-2 text-sm text-slate-600">
              <p>
                You have answered <strong>{answeredCount}</strong> out of{" "}
                <strong>{totalQuestions}</strong> questions.
              </p>
              {answeredCount < totalQuestions && (
                <p className="text-rose-600 text-xs font-semibold bg-rose-50 p-2 rounded-lg border border-rose-200">
                  Warning: You still have {totalQuestions - answeredCount} unanswered questions. Unanswered questions receive 0 points.
                </p>
              )}
              <p>Are you sure you want to finalize your examination now?</p>
            </div>
            <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowConfirmModal(false)}
                disabled={submittingExam}
              >
                Continue Answering
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={() => handleFinalSubmit("COMPLETED")}
                loading={submittingExam}
              >
                Yes, Finalize & Submit
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
