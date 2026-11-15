import { useState, useEffect } from "react"
import { LiveTelemetry } from "../types/sdn"
import { getSdnTelemetry } from "../lib/api"
import { WebSocketClient } from "../lib/ws"

const DEFAULT_STATE: LiveTelemetry = {
  available: false,
  stale: false,
  controller_connected: false,
  switch_count: 0,
  port_stats: [],
  congestion_state: "DISCONNECTED",
  policy_active: false,
  queue_assignment: null,
  policy_events: [],
  timestamp: null,
}

export function useSdnTelemetry() {
  const [telemetry, setTelemetry] = useState<LiveTelemetry>(DEFAULT_STATE)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchFresh = async () => {
    try {
      const data = await getSdnTelemetry()
      setTelemetry(data)
      setError(null)
    } catch (err: any) {
      setError(err.message || "Failed to fetch telemetry")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchFresh()

    // Setup WebSocket connection for live telemetry stream
    const ws = new WebSocketClient("/ws/sdn/monitor", (msg) => {
      if (msg.type === "telemetry") {
        setTelemetry(msg)
        setLoading(false)
      }
    })

    // Also fallback to periodic 3s polling in case WS is unavailable or disconnected
    const interval = setInterval(fetchFresh, 3000)

    return () => {
      ws.disconnect()
      clearInterval(interval)
    }
  }, [])

  return { telemetry, loading, error, refresh: fetchFresh }
}
