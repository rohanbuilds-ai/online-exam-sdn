import React from "react"
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { ExamProvider } from "./context/ExamContext"
import { AppShell } from "./components/layout/AppShell"
import { LoginPage } from "./pages/student/LoginPage"
import { InstructionsPage } from "./pages/student/InstructionsPage"
import { ExamPage } from "./pages/student/ExamPage"
import { ResultPage } from "./pages/student/ResultPage"
import { AdminDashboard } from "./pages/admin/AdminDashboard"
import { NetworkMonitor } from "./pages/sdn/NetworkMonitor"

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <ExamProvider>
        <AppShell>
          <Routes>
            {/* Student Exam Workflow */}
            <Route path="/" element={<LoginPage />} />
            <Route path="/exam/instructions" element={<InstructionsPage />} />
            <Route path="/exam" element={<ExamPage />} />
            <Route path="/exam/result" element={<ResultPage />} />

            {/* Admin Oversight */}
            <Route path="/admin" element={<AdminDashboard />} />

            {/* SDN Telemetry & Operations */}
            <Route path="/sdn" element={<NetworkMonitor />} />

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AppShell>
      </ExamProvider>
    </BrowserRouter>
  )
}

export default App
