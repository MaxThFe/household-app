import { useMemo, useState, type PointerEvent } from 'react'

export interface ChartSeries {
  key: string
  label: string
  color: string
  points: [number, number][]  // [unix seconds, value]
}

interface Props {
  series: ChartSeries[]
  unit: string
  start: number
  end: number
  /** Break the line across gaps wider than this many seconds. */
  gapSeconds: number
}

const W = 440
const H = 190
const PAD = { top: 10, right: 10, bottom: 22, left: 36 }
const PLOT_W = W - PAD.left - PAD.right
const PLOT_H = H - PAD.top - PAD.bottom

function niceTicks(min: number, max: number, count = 4) {
  const span = max - min || 1
  const mag = Math.pow(10, Math.floor(Math.log10(span / count)))
  const norm = span / count / mag
  const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag
  const lo = Math.floor(min / step) * step
  const hi = Math.ceil(max / step) * step
  const ticks: number[] = []
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Number(v.toFixed(6)))
  return { lo, hi, ticks }
}

function formatTime(ts: number, spanSeconds: number) {
  const d = new Date(ts * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return spanSeconds <= 48 * 3600
    ? `${pad(d.getHours())}:${pad(d.getMinutes())}`
    : `${pad(d.getDate())}.${pad(d.getMonth() + 1)}`
}

export default function LineChart({ series, unit, start, end, gapSeconds }: Props) {
  const [cursor, setCursor] = useState<number | null>(null)

  const active = series.filter(s => s.points.length > 0)
  const span = Math.max(1, end - start)

  const scale = useMemo(() => {
    const values = active.flatMap(s => s.points.map(p => p[1]))
    if (values.length === 0) return null
    const { lo, hi, ticks } = niceTicks(Math.min(...values), Math.max(...values))
    const x = (ts: number) => PAD.left + ((ts - start) / span) * PLOT_W
    const y = (v: number) => PAD.top + (1 - (v - lo) / (hi - lo || 1)) * PLOT_H
    return { x, y, ticks }
  }, [active, start, span])

  if (!scale) {
    return (
      <div className="card-dashed" style={{ padding: 24, textAlign: 'center', fontSize: 13 }}>
        No readings in this range
      </div>
    )
  }

  const xTicks = [0, 0.25, 0.5, 0.75, 1].map(f => start + f * span)

  // The value each series shows in the readout: at the cursor, else the latest.
  const readout = active.map(s => {
    if (cursor === null) return { ...s, value: s.points[s.points.length - 1][1] }
    let best = s.points[0]
    for (const p of s.points) {
      if (Math.abs(p[0] - cursor) < Math.abs(best[0] - cursor)) best = p
    }
    return { ...s, value: Math.abs(best[0] - cursor) <= gapSeconds ? best[1] : null }
  })

  const onPointer = (e: PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const fx = ((e.clientX - rect.left) / rect.width) * W
    if (fx < PAD.left || fx > W - PAD.right) return setCursor(null)
    setCursor(start + ((fx - PAD.left) / PLOT_W) * span)
  }

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 6, minHeight: 18 }}>
        {readout.map(s => (
          <span key={s.key} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
            <span style={{ width: 8, height: 8, borderRadius: 4, background: s.color }} />
            <span style={{ color: 'var(--text-secondary)' }}>{s.label}</span>
            <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
              {s.value === null ? '–' : `${s.value.toFixed(1)}${unit}`}
            </span>
          </span>
        ))}
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: '100%', display: 'block', touchAction: 'pan-y' }}
        onPointerDown={onPointer}
        onPointerMove={e => { if (e.buttons || e.pointerType === 'touch') onPointer(e) }}
        onPointerLeave={() => setCursor(null)}
        onPointerUp={() => setCursor(null)}
      >
        {scale.ticks.map(v => (
          <g key={v}>
            <line
              x1={PAD.left} x2={W - PAD.right} y1={scale.y(v)} y2={scale.y(v)}
              stroke="var(--border)" strokeWidth={1}
            />
            <text
              x={PAD.left - 6} y={scale.y(v) + 3} textAnchor="end"
              fontSize={9} fill="var(--text-muted)"
            >
              {v}
            </text>
          </g>
        ))}

        {xTicks.map((ts, i) => (
          <text
            key={ts} x={scale.x(ts)} y={H - 6}
            textAnchor={i === 0 ? 'start' : i === xTicks.length - 1 ? 'end' : 'middle'}
            fontSize={9} fill="var(--text-muted)"
          >
            {formatTime(ts, span)}
          </text>
        ))}

        {active.map(s => {
          let d = ''
          s.points.forEach((p, i) => {
            const gap = i > 0 && p[0] - s.points[i - 1][0] > gapSeconds
            d += `${i === 0 || gap ? 'M' : 'L'}${scale.x(p[0]).toFixed(1)} ${scale.y(p[1]).toFixed(1)}`
          })
          return (
            <path
              key={s.key} d={d} fill="none" stroke={s.color}
              strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
            />
          )
        })}

        {cursor !== null && (
          <line
            x1={scale.x(cursor)} x2={scale.x(cursor)} y1={PAD.top} y2={PAD.top + PLOT_H}
            stroke="var(--text-muted)" strokeWidth={1} strokeDasharray="3 3"
          />
        )}
        {cursor !== null && readout.map(s => (
          s.value === null ? null : (
            <circle
              key={s.key} cx={scale.x(cursor)} cy={scale.y(s.value)} r={4}
              fill={s.color} stroke="var(--bg-card)" strokeWidth={2}
            />
          )
        ))}
      </svg>
    </div>
  )
}
