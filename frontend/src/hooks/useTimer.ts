import { useState, useEffect, useRef } from "react"

export function useTimer(initialSeconds: number, onExpire?: () => void) {
  const [seconds, setSeconds] = useState(initialSeconds)
  const [isWarning, setIsWarning] = useState(false)
  const onExpireRef = useRef(onExpire)
  onExpireRef.current = onExpire

  // Sync when initialSeconds changes from server
  useEffect(() => {
    if (initialSeconds > 0) {
      setSeconds(initialSeconds)
    }
  }, [initialSeconds])

  useEffect(() => {
    if (seconds <= 0) {
      if (onExpireRef.current) {
        onExpireRef.current()
      }
      return
    }

    setIsWarning(seconds <= 60)

    const interval = setInterval(() => {
      setSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(interval)
          if (onExpireRef.current) {
            onExpireRef.current()
          }
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [seconds])

  return {
    remainingSeconds: seconds,
    isWarning,
    syncWithServer: (newSeconds: number) => setSeconds(newSeconds),
  }
}
