import React, { createContext, useContext, useState } from "react"
import { AuthResponse, ExamResult } from "../types/exam"

interface ExamContextType {
  authData: AuthResponse | null
  setAuthData: (data: AuthResponse | null) => void
  examResult: ExamResult | null
  setExamResult: (result: ExamResult | null) => void
  resetExam: () => void
}

const ExamContext = createContext<ExamContextType | undefined>(undefined)

export const ExamProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [authData, setAuthDataState] = useState<AuthResponse | null>(() => {
    const saved = sessionStorage.getItem("sdn_exam_auth")
    return saved ? JSON.parse(saved) : null
  })

  const [examResult, setExamResultState] = useState<ExamResult | null>(() => {
    const saved = sessionStorage.getItem("sdn_exam_result")
    return saved ? JSON.parse(saved) : null
  })

  const setAuthData = (data: AuthResponse | null) => {
    setAuthDataState(data)
    if (data) {
      sessionStorage.setItem("sdn_exam_auth", JSON.stringify(data))
    } else {
      sessionStorage.removeItem("sdn_exam_auth")
    }
  }

  const setExamResult = (result: ExamResult | null) => {
    setExamResultState(result)
    if (result) {
      sessionStorage.setItem("sdn_exam_result", JSON.stringify(result))
    } else {
      sessionStorage.removeItem("sdn_exam_result")
    }
  }

  const resetExam = () => {
    setAuthData(null)
    setExamResult(null)
    sessionStorage.removeItem("sdn_exam_auth")
    sessionStorage.removeItem("sdn_exam_result")
  }

  return (
    <ExamContext.Provider
      value={{
        authData,
        setAuthData,
        examResult,
        setExamResult,
        resetExam,
      }}
    >
      {children}
    </ExamContext.Provider>
  )
}

export function useExam() {
  const ctx = useContext(ExamContext)
  if (!ctx) {
    throw new Error("useExam must be used within an ExamProvider")
  }
  return ctx
}
