import React from "react"
import { cn } from "../../lib/utils"

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number // 0 to 100
  color?: "indigo" | "emerald" | "rose" | "amber"
}

export const Progress: React.FC<ProgressProps> = ({
  value,
  color = "indigo",
  className,
  ...props
}) => {
  const clamped = Math.min(100, Math.max(0, value))

  const colors = {
    indigo: "bg-indigo-600",
    emerald: "bg-emerald-500",
    rose: "bg-rose-500",
    amber: "bg-amber-500",
  }

  return (
    <div
      className={cn("w-full bg-slate-100 rounded-full h-2.5 overflow-hidden", className)}
      {...props}
    >
      <div
        className={cn("h-full transition-all duration-300", colors[color])}
        style={{ width: `${clamped}%` }}
      />
    </div>
  )
}
