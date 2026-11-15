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

// Admin Key Access Management
const DEFAULT_ADMIN_KEY = "sdn-admin-key-2026"

export function getAdminKey(): string {
  try {
    return localStorage.getItem("sdn_admin_key") || import.meta.env.VITE_ADMIN_API_KEY || DEFAULT_ADMIN_KEY
  } catch {
    return DEFAULT_ADMIN_KEY
  }
}

export function setAdminKey(key: string): void {
  try {
    localStorage.setItem("sdn_admin_key", key)
  } catch {
    // ignore local storage error
  }
}

// Admin API (protected with X-Admin-Key)
export async function getAdminStats(adminKey?: string): Promise<AdminStats> {
  const key = adminKey || getAdminKey()
  return request<AdminStats>("/api/admin/stats", {
    headers: { "X-Admin-Key": key },
  })
}

export async function getAdminResults(adminKey?: string): Promise<StudentResultRecord[]> {
  const key = adminKey || getAdminKey()
  return request<StudentResultRecord[]>("/api/admin/results", {
    headers: { "X-Admin-Key": key },
  })
}

export async function getAdminSessions(adminKey?: string): Promise<ActiveSession[]> {
  const key = adminKey || getAdminKey()
  return request<ActiveSession[]>("/api/admin/sessions", {
    headers: { "X-Admin-Key": key },
  })
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
