import { useEffect } from 'react'

interface ToastProps {
  message: string
  onUndo: () => void
  onExpire: () => void
  durationMs?: number
}

export function Toast({ message, onUndo, onExpire, durationMs = 3000 }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onExpire, durationMs)
    return () => clearTimeout(timer)
  }, [onExpire, durationMs])

  return (
    <div className="toast">
      <span>{message}</span>
      <button onClick={onUndo}>Undo</button>
    </div>
  )
}
