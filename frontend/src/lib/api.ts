import {
  AuthRequest,
  AuthResponse,
  Question,
  AnswerRequest,
  AnswerAck,
  ExamResult,
  AdminStats,
  StudentResultRecord,
  ActiveSession
} from "../types/exam"
import { LiveTelemetry, HistoricalResults } from "../types/sdn"

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  }

  const res = await fetch(url, { ...options, headers })
  if (!res.ok) {
    let errMessage = `HTTP error ${res.status}`
    try {
      const errJson = await res.json()
      if (errJson.detail && typeof errJson.detail === "object" && errJson.detail.error) {
        errMessage = errJson.detail.error
      } else if (typeof errJson.detail === "string") {
        errMessage = errJson.detail
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(errMessage)
  }
  return res.json() as Promise<T>
}

// Student Exam API
export async function authStudent(data: AuthRequest): Promise<AuthResponse> {
  return request<AuthResponse>("/api/exam/auth", {
    method: "POST",
    body: JSON.stringify(data),
  })
}

export async function getQuestion(sessionId: string): Promise<Question> {
  return request<Question>("/api/exam/question", {
    headers: { "X-Session-ID": sessionId },
  })
}

export async function submitAnswer(
  sessionId: string,
  data: AnswerRequest
): Promise<AnswerAck> {
  return request<AnswerAck>("/api/exam/answer", {
    method: "POST",
    headers: { "X-Session-ID": sessionId },
    body: JSON.stringify(data),
  })
}

export async function submitExam(sessionId: string): Promise<ExamResult> {
  return request<ExamResult>("/api/exam/submit", {
    method: "POST",
    headers: { "X-Session-ID": sessionId },
  })
}

export async function pingExam(sessionId: string): Promise<{ remaining_seconds: number | null }> {
  return request<{ remaining_seconds: number | null }>("/api/exam/ping", {
    headers: { "X-Session-ID": sessionId },
  })
}

// Admin API
export async function getAdminStats(): Promise<AdminStats> {
  return request<AdminStats>("/api/admin/stats")
}

export async function getAdminResults(): Promise<StudentResultRecord[]> {
  return request<StudentResultRecord[]>("/api/admin/results")
}

export async function getAdminSessions(): Promise<ActiveSession[]> {
  return request<ActiveSession[]>("/api/admin/sessions")
}

// SDN API
export async function getSdnTelemetry(): Promise<LiveTelemetry> {
  return request<LiveTelemetry>("/api/sdn/telemetry")
}

export async function getSdnHistory(): Promise<HistoricalResults> {
  return request<HistoricalResults>("/api/sdn/history")
}

export async function getHealth(): Promise<{ status: string; exam_server_reachable: boolean; timestamp: number }> {
  return request<{ status: string; exam_server_reachable: boolean; timestamp: number }>("/api/health")
}
