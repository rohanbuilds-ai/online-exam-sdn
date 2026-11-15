import React, { useEffect, useState } from "react"
import { Link, useLocation } from "react-router-dom"
import { Network, Activity, ShieldCheck, User, Server } from "lucide-react"
import { getHealth } from "../../lib/api"
import { Badge } from "../ui/Badge"

export const AppShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation()
  const [serverOnline, setServerOnline] = useState<boolean | null>(null)

  useEffect(() => {
    const check = async () => {
      try {
        const res = await getHealth()
        setServerOnline(res.exam_server_reachable)
      } catch {
        setServerOnline(false)
      }
    }
    check()
    const intv = setInterval(check, 10000)
    return () => clearInterval(intv)
  }, [])

  const navLinks = [
    { to: "/", label: "Student Portal", icon: User },
    { to: "/admin", label: "Admin Dashboard", icon: ShieldCheck },
    { to: "/sdn", label: "SDN Network Operations", icon: Activity },
  ]

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
      {/* Top Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-sm shadow-indigo-200">
              <Network className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-900 tracking-tight leading-none">
                SDN Exam Network
              </h1>
              <p className="text-xs text-slate-500 font-medium mt-0.5">
                TCP Socket + OpenFlow 1.3 QoS
              </p>
            </div>
          </div>

          {/* Navigation Bar */}
          <nav className="flex items-center gap-1 sm:gap-2">
            {navLinks.map((item) => {
              const Icon = item.icon
              const active =
                item.to === "/"
                  ? location.pathname === "/" || location.pathname.startsWith("/exam")
                  : location.pathname === item.to
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                    active
                      ? "bg-indigo-50 text-indigo-700 shadow-xs"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span className="hidden sm:inline">{item.label}</span>
                </Link>
              )
            })}
          </nav>

          {/* Health Indicator */}
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 bg-slate-100 px-2.5 py-1 rounded-full text-xs font-medium text-slate-600 border border-slate-200">
              <Server className="h-3.5 w-3.5 text-slate-500" />
              <span className="hidden md:inline">TCP Server:</span>
              {serverOnline === null ? (
                <Badge variant="neutral" className="py-0 px-1.5 text-[10px]">Checking</Badge>
              ) : serverOnline ? (
                <Badge variant="success" className="py-0 px-1.5 text-[10px]">Online (Port 5000)</Badge>
              ) : (
                <Badge variant="warning" className="py-0 px-1.5 text-[10px]">Standby</Badge>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-4 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-2">
          <span>SDN-Based Online Examination System — OpenFlow 1.3 Adaptive QoS Prototype</span>
          <span className="font-mono">TCP Port 5000 • Controller Port 6653 • Gateway Port 8000</span>
        </div>
      </footer>
    </div>
  )
}
