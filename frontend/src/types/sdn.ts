// SDN telemetry TypeScript interfaces matching real controller & API payloads

export interface SwitchInfo {
  dpid: number | null
  address: [string, number] | string
  ready: boolean
}

export interface PortStat {
  port_no: number
  tx_rate_mbps?: number
  rx_rate_mbps?: number
  utilization_percent?: number
  tx_bytes?: number
  rx_bytes?: number
  tx_packets?: number
  rx_packets?: number
  tx_dropped?: number
  rx_dropped?: number
  tx_errors?: number
  rx_errors?: number
}

export interface PolicyEvent {
  timestamp: number
  port_no: number
  utilization_percent: number
  previous_state: string
  new_state: 'CONGESTED' | 'NORMAL' | string
  action: string
}

export interface LiveTelemetry {
  available: boolean
  stale: boolean
  controller_connected: boolean
  switch_count: number
  switches?: SwitchInfo[]
  port_stats: PortStat[]
  congestion_state: 'NORMAL' | 'CONGESTED' | 'DISCONNECTED' | 'UNKNOWN' | string
  policy_active: boolean
  queue_assignment: number | null
  policy_events: PolicyEvent[]
  timestamp: number | null
}

export interface BenchmarkRecord {
  architecture: string
  concurrency: number
  condition: string
  avg_latency_ms: number
  p95_latency_ms: number
  throughput_req_per_sec: number
  packet_loss_percent: number
  link_utilization_percent: number
  completion_rate_percent: number
  jains_fairness_index: number
  sdn_policy_active?: boolean
}

export interface HistoricalResults {
  baseline: BenchmarkRecord[]
  dynamic: BenchmarkRecord[]
}
