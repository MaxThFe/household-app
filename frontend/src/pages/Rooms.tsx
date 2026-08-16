import { useState, useEffect, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, SensorHistory, SensorSeriesInfo } from '../api/client'
import LineChart, { ChartSeries } from '../components/LineChart'

// Colour identifies the room; the two metrics live in separate charts, so a
// single fixed order is all that is needed. Darker than the app's accents so
// white pill text clears 4.5:1 (5.4 / 6.9 / 5.3); still passes the CVD,
// chroma and lightness-band checks.
const ROOM_COLORS = ['#B8431F', '#534AB7', '#0F7A55']

/** Local datetime in the format <input type="datetime-local"> expects. */
function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function Rooms() {
  const navigate = useNavigate()

  // The whole view lives in the query string: range and hidden series. Each
  // change pushes a history entry, so back returns to the previous chart and
  // the URL can be shared or bookmarked as-is.
  const [params, setParams] = useSearchParams()

  const defaults = useMemo(() => ({
    from: toLocalInput(new Date(Date.now() - 24 * 3600_000)),
    to: toLocalInput(new Date()),
  }), [])

  const start = params.get('from') ?? defaults.from
  const end = params.get('to') ?? defaults.to
  const off = useMemo(
    () => new Set((params.get('hide') ?? '').split(',').filter(Boolean)),
    [params],
  )

  const [available, setAvailable] = useState<SensorSeriesInfo[]>([])

  // Open on a range that actually holds data: the last 24 h, or the whole
  // history when there is less than that. Written once the extent is known, so
  // a fresh install does not stare at an empty 24 h window. Replace rather than
  // push, or back would land on the bare /rooms again.
  useEffect(() => {
    if (params.get('from') && params.get('to')) return
    if (!available.length) return
    const starts = available.map(s => s.first_ts).filter((t): t is number => t !== null)
    const next = new URLSearchParams(params)
    next.set('from', starts.length
      ? toLocalInput(new Date(Math.max(Date.now() - 24 * 3600_000, Math.min(...starts) * 1000)))
      : defaults.from)
    next.set('to', defaults.to)
    setParams(next, { replace: true })
  }, [available])

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next)
  }

  const [history, setHistory] = useState<SensorHistory[]>([])

  // Rooms, metrics and units all come from /sensors/series, so nothing about
  // the sensor set is restated here — a new metric shows up on its own.
  const rooms = useMemo(
    () => [...new Set(available.map(s => s.room))],
    [available],
  )

  const metrics = useMemo(() => {
    const units = new Map<string, string>()
    available.forEach(s => { if (!units.has(s.metric)) units.set(s.metric, s.unit) })
    return [...units].map(([key, unit]) => ({
      key,
      unit,
      label: key.charAt(0).toUpperCase() + key.slice(1),
    }))
  }, [available])

  useEffect(() => {
    api.sensors.series().then(setAvailable).catch(() => {})
  }, [])

  const wanted = available
    .map(s => `${s.room}:${s.metric}`)
    .filter(key => !off.has(key))
  const wantedKey = wanted.join(',')

  useEffect(() => {
    if (!wanted.length) return setHistory([])
    const from = new Date(start)
    const to = new Date(end)
    if (!(from < to)) return
    api.sensors.history(from, to, wanted).then(setHistory).catch(() => {})
    // wantedKey stands in for the wanted array, which is rebuilt every render.
  }, [wantedKey, start, end])

  const toggle = (key: string) => {
    const next = new Set(off)
    next.has(key) ? next.delete(key) : next.add(key)
    update('hide', [...next].join(','))
  }

  const from = new Date(start).getTime() / 1000
  const to = new Date(end).getTime() / 1000
  // Break lines across gaps a few samples wide, so sensor silence stays visible.
  const gapSeconds = Math.max(180, ((to - from) / 500) * 3)

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button onClick={() => navigate('/')} style={{ display: 'flex', padding: 4, marginLeft: -4, color: 'var(--text-secondary)' }}>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M12 4l-6 6 6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <p style={{ fontSize: 22, fontWeight: 500 }}>Rooms</p>
        </div>
      </div>

      <div style={{ padding: '16px 20px' }}>
        {/* Full width rather than side by side: two datetime-locals in a 480px
            column are too narrow to show the date and the clock together. */}
        <div style={{ marginBottom: 16 }}>
          {([['From', start, 'from'], ['To', end, 'to']] as const).map(([label, value, key]) => (
            <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <span className="section-label" style={{ width: 38, margin: 0 }}>{label}</span>
              <input
                type="datetime-local" className="form-input" style={{ flex: 1 }} value={value}
                onChange={e => update(key, e.target.value)}
              />
            </label>
          ))}
        </div>

        {metrics.map(metric => {
          const series: ChartSeries[] = rooms
            .filter(room => !off.has(`${room}:${metric.key}`))
            .map(room => ({
              key: `${room}:${metric.key}`,
              label: room,
              color: ROOM_COLORS[rooms.indexOf(room) % ROOM_COLORS.length],
              points: history.find(h => h.room === room && h.metric === metric.key)?.points ?? [],
            }))

          return (
            <div key={metric.key} style={{ marginBottom: 20 }}>
              <p className="section-label">{metric.label}</p>

              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', margin: '6px 0 10px' }}>
                {/* The pills are the legend: an active one is filled with the
                    line's colour, so the chart needs no separate key. */}
                {rooms.map((room, i) => {
                  const key = `${room}:${metric.key}`
                  const hidden = off.has(key)
                  return (
                    <button
                      key={key}
                      className="pill"
                      onClick={() => toggle(key)}
                      style={{
                        fontWeight: 500,
                        color: hidden ? '#6B5D4D' : '#FFFFFF',
                        background: hidden
                          ? 'var(--bg-inactive)'
                          : ROOM_COLORS[i % ROOM_COLORS.length],
                      }}
                    >
                      {room}
                    </button>
                  )
                })}
              </div>

              {series.length === 0 ? (
                <div className="card-dashed" style={{ padding: 24, textAlign: 'center', fontSize: 13 }}>
                  No rooms selected
                </div>
              ) : (
                <div className="card" style={{ padding: '12px 10px' }}>
                  <LineChart
                    series={series}
                    unit={metric.unit}
                    start={from}
                    end={to}
                    gapSeconds={gapSeconds}
                    // Half a degree matters; half a percent of humidity does not.
                    decimals={metric.key === 'temperature' ? 1 : 0}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
