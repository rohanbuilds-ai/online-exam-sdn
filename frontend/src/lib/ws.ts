const WS_BASE = import.meta.env.VITE_WS_URL || "ws://localhost:8000"

export type MessageHandler = (data: any) => void

export class WebSocketClient {
  private url: string
  private ws: WebSocket | null = null
  private onMessage: MessageHandler
  private shouldReconnect: boolean = true
  private reconnectTimeout: any = null

  constructor(path: string, onMessage: MessageHandler) {
    this.url = `${WS_BASE}${path}`
    this.onMessage = onMessage
    this.connect()
  }

  private connect() {
    try {
      this.ws = new WebSocket(this.url)

      this.ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data)
          this.onMessage(parsed)
        } catch {
          // ignore invalid json
        }
      }

      this.ws.onclose = () => {
        if (this.shouldReconnect) {
          this.reconnectTimeout = setTimeout(() => this.connect(), 3000)
        }
      }

      this.ws.onerror = () => {
        if (this.ws) {
          this.ws.close()
        }
      }
    } catch {
      if (this.shouldReconnect) {
        this.reconnectTimeout = setTimeout(() => this.connect(), 3000)
      }
    }
  }

  public send(data: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(typeof data === "string" ? data : JSON.stringify(data))
    }
  }

  public disconnect() {
    this.shouldReconnect = false
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout)
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
}
