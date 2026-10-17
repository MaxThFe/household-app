import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, isTaskDue, RecurUnit, Task } from '../api/client'
import { Modal } from '../components/Modal'
import { TaskRow, useTaskCompletion } from '../components/TaskRow'

// The repeat presets, in the order they are offered. "Custom" is the escape
// hatch for everything else — every 3 days, every 2 weeks, every 6 months.
const PRESETS: { label: string; unit: RecurUnit | null }[] = [
  { label: 'Once', unit: null },
  { label: 'Daily', unit: 'day' },
  { label: 'Weekly', unit: 'week' },
  { label: 'Monthly', unit: 'month' },
]

const UNIT_LABELS: Record<RecurUnit, string> = { day: 'days', week: 'weeks', month: 'months' }

interface Repeat {
  unit: RecurUnit | null
  every: number
}

function RepeatPicker({ value, onChange }: { value: Repeat; onChange: (r: Repeat) => void }) {
  // A multiplier above 1 can only have come from the custom row, so the pills
  // need no state of their own to stay in sync with an edited task.
  const custom = value.unit !== null && value.every > 1

  return (
    <div className="form-group">
      <label className="form-label">Repeat</label>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {PRESETS.map(preset => {
          const active = !custom && value.unit === preset.unit
          return (
            <button
              key={preset.label}
              className={`pill ${active ? 'pill-active' : 'pill-inactive'}`}
              onClick={() => onChange({ unit: preset.unit, every: 1 })}
            >
              {preset.label}
            </button>
          )
        })}
        <button
          className={`pill ${custom ? 'pill-active' : 'pill-inactive'}`}
          onClick={() => onChange({ unit: value.unit ?? 'week', every: 2 })}
        >
          Custom
        </button>
      </div>

      {custom && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10 }}>
          <span style={{ fontSize: 14, color: 'var(--text-secondary)' }}>Every</span>
          <input
            className="form-input"
            type="number"
            min={2}
            max={99}
            style={{ width: 72 }}
            value={value.every}
            onChange={e => {
              // Below 2 is a preset, so keep the custom row out of that range.
              const every = Math.min(99, Math.max(2, parseInt(e.target.value) || 2))
              onChange({ ...value, every })
            }}
          />
          <select
            className="form-input"
            style={{ flex: 1 }}
            value={value.unit ?? 'week'}
            onChange={e => onChange({ ...value, unit: e.target.value as RecurUnit })}
          >
            {(Object.keys(UNIT_LABELS) as RecurUnit[]).map(unit => (
              <option key={unit} value={unit}>{UNIT_LABELS[unit]}</option>
            ))}
          </select>
        </div>
      )}
    </div>
  )
}

// --- Add / edit modal, one form for both ---
interface TaskModalProps {
  task: Task | null
  onClose: () => void
  onSaved: () => void
}

function TaskModal({ task, onClose, onSaved }: TaskModalProps) {
  const [title, setTitle] = useState(task?.title ?? '')
  const [repeat, setRepeat] = useState<Repeat>({
    unit: task?.recur_unit ?? null,
    every: task?.recur_every ?? 1,
  })
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    if (!title.trim()) return
    setSaving(true)
    const data = {
      title: title.trim(),
      recur_unit: repeat.unit,
      recur_every: repeat.unit ? repeat.every : 1,
    }
    try {
      if (task) await api.tasks.update(task.id, data)
      else await api.tasks.add(data)
      onSaved()
      onClose()
    } catch {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!task) return
    setSaving(true)
    try {
      await api.tasks.delete(task.id)
      onSaved()
      onClose()
    } catch {
      setSaving(false)
    }
  }

  return (
    <Modal
      title={task ? 'Edit task' : 'Add task'}
      onClose={onClose}
      footer={
        <>
          {task && (
            <button className="btn-danger" onClick={handleDelete} disabled={saving}>
              Delete
            </button>
          )}
          <button className="btn-primary" onClick={handleSave} disabled={saving || !title.trim()}>
            {saving ? 'Saving…' : task ? 'Save' : 'Add'}
          </button>
        </>
      }
    >
      <div className="form-group">
        <label className="form-label">Task</label>
        <input
          className="form-input"
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="e.g. Water the plants"
          autoFocus
        />
      </div>
      <RepeatPicker value={repeat} onChange={setRepeat} />
    </Modal>
  )
}

// --- Main tasks page ---
export default function Tasks() {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [editTask, setEditTask] = useState<Task | null>(null)

  const load = useCallback(() => {
    api.tasks.list()
      .then(data => { setTasks(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const { pendingIds, check, toastNode } = useTaskCompletion(load)

  // A task that has been done is off the list: a one-off for good, a recurring
  // chore until its period is up.
  const due = tasks.filter(t => isTaskDue(t))

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              onClick={() => navigate('/')}
              style={{ display: 'flex', padding: 4, marginLeft: -4, color: 'var(--text-secondary)' }}
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M12 4l-6 6 6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <div>
              <p style={{ fontSize: 22, fontWeight: 500 }}>Tasks</p>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
                {due.length} to do
              </p>
            </div>
          </div>
          <button className="add-btn" title="Add task" onClick={() => setShowAdd(true)}>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M9 3v12M3 9h12" stroke="var(--text-on-dark)" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>

      <div style={{ padding: '16px 20px' }}>
        {loading ? (
          <div className="loading">Loading…</div>
        ) : due.length === 0 ? (
          <div className="empty-state">
            <p style={{ fontSize: 32, marginBottom: 12 }}>🧹</p>
            <p>Nothing to do — add a task with +</p>
          </div>
        ) : (
          <div className="list-card">
            {due.map(task => (
              <TaskRow
                key={task.id}
                task={task}
                pending={pendingIds.has(task.id)}
                onCheck={check}
                onEdit={setEditTask}
              />
            ))}
          </div>
        )}
      </div>

      {showAdd && <TaskModal task={null} onClose={() => setShowAdd(false)} onSaved={load} />}
      {editTask && (
        <TaskModal task={editTask} onClose={() => setEditTask(null)} onSaved={load} />
      )}
      {toastNode}
    </div>
  )
}
