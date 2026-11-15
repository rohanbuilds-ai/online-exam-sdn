import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatTime(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return "00:00"
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`
}

export function formatDateTime(timestamp: number | string | null): string {
  if (!timestamp) return "—"
  const date = typeof timestamp === "number" ? new Date(timestamp * 1000) : new Date(timestamp)
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
}

export function formatPercent(val: number | null | undefined): string {
  if (val === null || val === undefined || isNaN(val)) return "0.0%"
  return `${val.toFixed(1)}%`
}

export function formatMbps(val: number | null | undefined): string {
  if (val === null || val === undefined || isNaN(val)) return "0.00 Mbps"
  return `${val.toFixed(2)} Mbps`
}
