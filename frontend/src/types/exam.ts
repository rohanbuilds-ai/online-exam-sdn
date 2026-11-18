// Exam domain TypeScript interfaces aligned with FastAPI and TCP server

export interface AuthRequest {
  student_id: string
  student_name: string
}

export interface AuthResponse {
  gateway_session_id: string
  student_id: string
  student_name: string
  total_questions: number
  exam_duration_sec: number
}

export interface Question {
  question_id: number
  number: number
  total: number
  category: string
  question: string
  options: string[]
  points: number
  remaining_seconds: number
}

export interface AnswerRequest {
  question_id: number
  selected_option: number
}

export interface AnswerAck {
  is_correct?: boolean
  points_awarded?: number
  explanation?: string
  remaining_seconds?: number
}

export interface ExamResult {
  session_id: string
  student_id: string
  student_name: string
  score: number
  total_points: number
  total_questions: number
  questions_answered: number
  percentage: number
  passed: boolean
  duration_taken_sec: number
  reason: string
}

export interface AdminStats {
  total_completed_exams: number
  average_percentage: number
  highest_percentage: number
  lowest_percentage: number
  active_sessions: number
}

export interface StudentResultRecord {
  session_id: string
  student_id: string
  name: string
  score: number
  total_points: number
  percentage: number
  status: 'COMPLETED' | 'TIME_EXPIRED' | 'DISCONNECTED' | 'ACTIVE' | string
  completed_at: number
}

export interface ActiveSession {
  id?: string
  gateway_session_id?: string
  student_id: string
  student_name: string
  started_at: number
}

export type ExamStatus = 'idle' | 'authenticating' | 'instructions' | 'active' | 'submitting' | 'completed' | 'error'
