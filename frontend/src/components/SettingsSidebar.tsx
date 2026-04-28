import { useState, useEffect, useCallback } from 'react'
import { api, VacuumScheduleEntry, dateISO, getMondayFromWeek, toISOWeek } from '../api/client'

interface Props {
  onClose: () => void
}

export function SettingsSidebar({ onClose }: Props) {
  const [schedule, setSchedule] = useState<VacuumScheduleEntry[]>([])
  const [editingDate, setEditingDate] = useState<string | null>(null)
  const [editTime, setEditTime] = useState('')

  const loadSchedule = useCallback(() => {
    const monday = getMondayFromWeek(toISOWeek(new Date()))
    const sunday = new Date(monday)
    sunday.setDate(monday.getDate() + 6)
    api.vacuum.schedule(dateISO(monday), dateISO(sunday))
      .then(setSchedule)
      .catch(() => {})
  }, [])

  useEffect(() => {
    loadSchedule()
  }, [loadSchedule])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  const formatDay = (dateStr: string) => {
    const d = new Date(dateStr + 'T00:00:00')
    return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
  }

  const isToday = (dateStr: string) => dateStr === dateISO(new Date())

  const handleDelete = async (date: string) => {
    await api.vacuum.deleteCleaning(date).catch(() => {})
    loadSchedule()
  }

  const handleRestore = async (date: string) => {
    await api.vacuum.restore(date).catch(() => {})
    loadSchedule()
  }

  const handleEditStart = (entry: VacuumScheduleEntry) => {
    setEditingDate(entry.date)
    setEditTime(entry.clean_time ?? '')
  }

  const handleEditSave = async () => {
    if (editingDate && editTime) {
      await api.vacuum.setOverride(editingDate, editTime).catch(() => {})
      setEditingDate(null)
      loadSchedule()
    }
  }

  const handleEditCancel = () => {
    setEditingDate(null)
  }

  return (
    <>
      <div className="sidebar-overlay" onClick={onClose} />
      <div className="sidebar-panel">
        <div className="sidebar-header">
          <span style={{ fontSize: 17, fontWeight: 500 }}>Larry's Schedule</span>
          <button onClick={onClose} style={{ fontSize: 20, color: 'var(--text-muted)', lineHeight: 1 }}>×</button>
        </div>
        <div className="sidebar-body">
          <p className="section-label">This week</p>
          <div style={{ background: 'var(--bg-card)', border: '0.5px solid var(--border)', borderRadius: 'var(--radius-card)', overflow: 'hidden' }}>
            {schedule.map(entry => {
              const deleted = entry.clean_time === null
              const overridden = !entry.is_default && !deleted

              if (editingDate === entry.date) {
                return (
                  <div key={entry.date} className="vacuum-row" style={{ flexDirection: 'column', alignItems: 'stretch', gap: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 14, fontWeight: isToday(entry.date) ? 600 : 400 }}>{formatDay(entry.date)}</span>
                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{entry.shift_type ?? 'Day off'}</span>
                    </div>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <input
                        type="time"
                        value={editTime}
                        onChange={e => setEditTime(e.target.value)}
                        className="form-input"
                        style={{ flex: 1, padding: '6px 10px', fontSize: 14 }}
                        autoFocus
                      />
                      <button
                        onClick={handleEditSave}
                        style={{ padding: '6px 12px', background: 'var(--bg-active)', color: 'var(--text-on-dark)', borderRadius: 8, fontSize: 13, fontWeight: 500 }}
                      >
                        Save
                      </button>
                      <button
                        onClick={handleEditCancel}
                        style={{ padding: '6px 12px', background: 'var(--bg-inactive)', color: 'var(--text-primary)', borderRadius: 8, fontSize: 13 }}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )
              }

              return (
                <div
                  key={entry.date}
                  className={`vacuum-row${deleted ? ' deleted' : ''}${overridden ? ' overridden' : ''}`}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                        {formatDay(entry.date)}, {entry.shift_type ?? 'Day off'}
                      </span>
                      {isToday(entry.date) && (
                        <span style={{ fontSize: 10, background: 'var(--bg-active)', color: 'var(--text-on-dark)', padding: '1px 6px', borderRadius: 8 }}>Today</span>
                      )}
                    </div>
                    <div style={{ marginTop: 3 }}>
                      {deleted ? (
                        <span style={{ fontSize: 14, color: 'var(--accent-red)' }}>No cleaning</span>
                      ) : (
                        <button
                          onClick={() => handleEditStart(entry)}
                          style={{ fontSize: 16, fontWeight: 500, color: overridden ? 'var(--accent-purple)' : 'var(--text-primary)', padding: 0 }}
                        >
                          {entry.clean_time}
                          {overridden && <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--text-muted)', marginLeft: 6 }}>edited</span>}
                        </button>
                      )}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                    {deleted ? (
                      <button
                        onClick={() => handleRestore(entry.date)}
                        title="Restore"
                        style={{ padding: 6, color: 'var(--accent-green)' }}
                      >
                        <RestoreIcon />
                      </button>
                    ) : (
                      <>
                        <button
                          onClick={() => handleDelete(entry.date)}
                          title="Remove cleaning"
                          style={{ padding: 6, color: 'var(--text-muted)' }}
                        >
                          <TrashIcon />
                        </button>
                        {overridden && (
                          <button
                            onClick={() => handleRestore(entry.date)}
                            title="Restore default"
                            style={{ padding: 6, color: 'var(--text-muted)' }}
                          >
                            <RestoreIcon />
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </>
  )
}

function TrashIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M3 4h10M6 4V3a1 1 0 011-1h2a1 1 0 011 1v1M5 4v8a1 1 0 001 1h4a1 1 0 001-1V4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function RestoreIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M2 7c1-3.5 4.5-5 7.5-3.5M14 9c-1 3.5-4.5 5-7.5 3.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M10 2l-.5 3.5L13 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M6 14l.5-3.5L3 12" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
