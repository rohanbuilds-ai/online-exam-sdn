import React from "react"
import { cn } from "../../lib/utils"

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "info" | "warning" | "danger" | "success"
  title?: string
}

export const Alert: React.FC<AlertProps> = ({
  children,
  title,
  variant = "info",
  className,
  ...props
}) => {
  const styles = {
    info: "bg-blue-50 border-blue-200 text-blue-900",
    warning: "bg-amber-50 border-amber-200 text-amber-900",
    danger: "bg-rose-50 border-rose-200 text-rose-900",
    success: "bg-emerald-50 border-emerald-200 text-emerald-900",
  }

  return (
    <div
      className={cn("p-4 rounded-xl border text-sm flex flex-col gap-1", styles[variant], className)}
      role="alert"
      {...props}
    >
      {title && <h4 className="font-semibold text-inherit">{title}</h4>}
      <div>{children}</div>
    </div>
  )
}
