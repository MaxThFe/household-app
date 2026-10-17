import { useState, useEffect, useCallback, useRef } from 'react'
import { api, recurrenceLabel, Task } from '../api/client'
import { Toast } from './Toast'

interface TaskRowProps {
  task: Task
  pending: boolean
  onCheck: (task: Task) => void
  onEdit: (task: Task) => void
}

export function TaskRow({ task, pending, onCheck, onEdit }: TaskRowProps) {
  const subtitle = recurrenceLabel(task)

  return (
    <div className="list-row" style={{ opacity: pending ? 0.4 : 1, transition: 'opacity 0.2s' }}>
      <input
        type="checkbox"
        className="checkbox"
        checked={pending}
        onChange={() => onCheck(task)}
      />
      <div style={{ flex: 1, cursor: 'pointer' }} onClick={() => onEdit(task)}>
        <p style={{ fontSize: 14, color: 'var(--text-primary)' }}>{task.title}</p>
        {subtitle && (
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>{subtitle}</p>
        )}
      </div>
    </div>
  )
}

/**
 * Tick-off with a 3s undo window, shared by the task page and the dashboard.
 *
 * The task is only sent to the server once the window closes, so undo is a
 * cleared timer rather than a second request — the same bargain the shopping
 * list makes. Returns the toast to render, so a caller only has to place it.
 */
export function useTaskCompletion(reload: () => void) {
  const [pendingIds, setPendingIds] = useState<Set<number>>(new Set())
  const [toast, setToast] = useState<Task | null>(null)
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map())

  const undo = useCallback((task: Task) => {
    const timer = timers.current.get(task.id)
    if (timer) {
      clearTimeout(timer)
      timers.current.delete(task.id)
    }
    setPendingIds(prev => { const s = new Set(prev); s.delete(task.id); return s })
    setToast(null)
  }, [])

  const check = useCallback((task: Task) => {
    if (timers.current.has(task.id)) return undo(task)

    setPendingIds(prev => new Set([...prev, task.id]))
    setToast(task)

    timers.current.set(task.id, setTimeout(async () => {
      timers.current.delete(task.id)
      setPendingIds(prev => { const s = new Set(prev); s.delete(task.id); return s })
      setToast(null)
      try {
        await api.tasks.complete(task.id)
      } finally {
        reload()
      }
    }, 3000))
  }, [reload, undo])

  // A timer still running at unmount would tick the task off with no row left
  // to undo from, so drop it and leave the task standing.
  useEffect(() => {
    const pending = timers.current
    return () => pending.forEach(clearTimeout)
  }, [])

  const toastNode = toast && (
    <Toast
      message={`"${toast.title}" done`}
      onUndo={() => undo(toast)}
      onExpire={() => setToast(null)}
    />
  )

  return { pendingIds, check, toastNode }
}
