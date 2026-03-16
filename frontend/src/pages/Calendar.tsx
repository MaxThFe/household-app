import { useState, useEffect, useCallback } from 'react'
import { api, CalendarEvent, toISOWeek, offsetWeek, getMondayFromWeek, formatDateRange, todayISO } from '../api/client'
import { Modal } from '../components/Modal'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function EventRow({ event, dark }: { event: CalendarEvent; dark?: boolean }) {
  return (
    <div className="calendar-event-row">
      <div className="shift-dot-sm" style={{ background: event.color }} />
      <p style={{ fontSize: 13, color: dark ? 'var(--text-on-dark)' : 'var(--text-primary)' }}>
        {event.title}
        {event.start_time && (
          <span style={{ color: dark ? 'var(--text-on-dark-muted)' : 'var(--text-muted)' }}>
            {' '}{event.start_time}{event.end_time ? ` – ${event.end_time}` : ''}
          </span>
        )}
      </p>
    </div>
  )
}

// --- Add event modal ---
interface AddEventModalProps {
  initialDate?: string
  onClose: () => void
  onSaved: () => void
}

function AddEventModal({ initialDate, onClose, onSaved }: AddEventModalProps) {
  const [title, setTitle] = useState('')
  const [date, setDate] = useState(initialDate ?? todayISO())
  const [startTime, setStartTime] = useState('')
  const [endTime, setEndTime] = useState('')
  const [allDay, setAllDay] = useState(false)
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    if (!title.trim()) return
    setSaving(true)
    try {
      await api.calendar.create({
        date,
        title: title.trim(),
        start_time: allDay ? undefined : startTime || undefined,
        end_time: allDay ? undefined : endTime || undefined,
        all_day: allDay ? 1 : 0,
      })
      onSaved()
      onClose()
    } catch {
      setSaving(false)
    }
  }

  return (
    <Modal
      title="Add event"
      onClose={onClose}
      footer={
        <button className="btn-primary" onClick={handleSave} disabled={saving || !title.trim()}>
          {saving ? 'Saving…' : 'Add event'}
        </button>
      }
    >
      <div className="form-group">
        <label className="form-label">Title</label>
        <input className="form-input" value={title} onChange={e => setTitle(e.target.value)} placeholder="Event name" autoFocus />
      </div>
      <div className="form-group">
        <label className="form-label">Date</label>
        <input className="form-input" type="date" value={date} onChange={e => setDate(e.target.value)} />
      </div>
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, cursor: 'pointer' }}>
        <input type="checkbox" checked={allDay} onChange={e => setAllDay(e.target.checked)} />
        <span style={{ fontSize: 14 }}>All day</span>
      </label>
      {!allDay && (
        <div style={{ display: 'flex', gap: 12 }}>
          <div className="form-group" style={{ flex: 1 }}>
            <label className="form-label">Start</label>
            <input className="form-input" type="time" value={startTime} onChange={e => setStartTime(e.target.value)} />
          </div>
          <div className="form-group" style={{ flex: 1 }}>
            <label className="form-label">End</label>
            <input className="form-input" type="time" value={endTime} onChange={e => setEndTime(e.target.value)} />
          </div>
        </div>
      )}
    </Modal>
  )
}

// --- Main calendar page ---

export default function CalendarPage() {
  const [week, setWeek] = useState(toISOWeek(new Date()))
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [showAddModal, setShowAddModal] = useState(false)
  const [addDate, setAddDate] = useState<string | undefined>()

  const today = todayISO()
  const monday = getMondayFromWeek(week)
  const sunday = new Date(monday)
  sunday.setDate(monday.getDate() + 6)

  const startStr = monday.toISOString().slice(0, 10)
  const endStr = sunday.toISOString().slice(0, 10)

  const loadEvents = useCallback(() => {
    api.calendar.list({ start: startStr, end: endStr })
      .then(setEvents)
      .catch(() => {})
  }, [startStr, endStr])

  useEffect(() => { loadEvents() }, [loadEvents])

  const days = DAYS.map((day, i) => {
    const d = new Date(monday)
    d.setDate(monday.getDate() + i)
    const date = d.toISOString().slice(0, 10)
    return {
      date,
      day,
      dateNum: d.getDate(),
      isToday: date === today,
      events: events.filter(e => e.date === date),
    }
  })

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p style={{ fontSize: 22, fontWeight: 500 }}>Calendar</p>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
              {formatDateRange(monday)}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button className="nav-btn" onClick={() => setWeek(w => offsetWeek(w, -1))}>
              <ChevronLeft />
            </button>
            <button className="nav-btn" onClick={() => setWeek(w => offsetWeek(w, 1))}>
              <ChevronRight />
            </button>
          </div>
        </div>
      </div>

      <div style={{ padding: '12px 20px' }}>
        {days.map(({ date, day, dateNum, isToday, events: dayEvents }) => {
          if (isToday) {
            return (
              <div key={date} className="card-today" style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <div style={{ minWidth: 36 }}>
                    <p style={{ fontSize: 11, color: 'var(--text-on-dark-muted)' }}>{day}</p>
                    <p style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-on-dark)' }}>{dateNum}</p>
                  </div>
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {dayEvents.length > 0 ? (
                      dayEvents.map(e => <EventRow key={e.id} event={e} dark />)
                    ) : (
                      <p style={{ fontSize: 13, color: 'var(--text-on-dark-muted)', fontStyle: 'italic' }}>No events</p>
                    )}
                  </div>
                </div>
              </div>
            )
          }

          return (
            <div key={date} className="card">
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                <div style={{ minWidth: 36 }}>
                  <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>{day}</p>
                  <p style={{ fontSize: 15, fontWeight: 500 }}>{dateNum}</p>
                </div>
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {dayEvents.length > 0 ? (
                    dayEvents.map(e => <EventRow key={e.id} event={e} />)
                  ) : (
                    <p style={{ fontSize: 13, color: 'var(--text-muted)', fontStyle: 'italic' }}>No events</p>
                  )}
                </div>
              </div>
            </div>
          )
        })}

        {/* Add event */}
        <div
          className="card-dashed"
          onClick={() => { setAddDate(undefined); setShowAddModal(true) }}
          style={{ marginTop: 4 }}
        >
          + Add event
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', gap: 12, marginTop: 14, flexWrap: 'wrap' }}>
          <LegendItem color="#1D9E75" label="Early shift" />
          <LegendItem color="#D85A30" label="Late shift" />
          <LegendItem color="#534AB7" label="Night / event" />
        </div>
      </div>

      {showAddModal && (
        <AddEventModal
          initialDate={addDate}
          onClose={() => setShowAddModal(false)}
          onSaved={loadEvents}
        />
      )}
    </div>
  )
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
      <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{label}</span>
    </div>
  )
}

function ChevronLeft() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M9 2L5 7l4 5" stroke="#6B5D4D" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function ChevronRight() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M5 2l4 5-4 5" stroke="#6B5D4D" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}
