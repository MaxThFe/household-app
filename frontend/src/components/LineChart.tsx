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
  /** Decimals for the value labels. The axis picks its own from the tick step. */
  decimals: number
}

const W = 440
const H = 210
// Right leaves room for the direct value labels, left/bottom for 13px ticks.
// Top leaves room for the cursor's time stamp above the plot.
const PAD = { top: 24, right: 46, bottom: 30, left: 44 }
const TICK_SIZE = 13
const LABEL_SIZE = 13
// Minimum vertical spacing between two direct labels before they get nudged.
const LABEL_GAP = 14
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
  // Decimals implied by the step, so every tick is written to the same width
  // (21.0 / 21.5 / 22.0, never 21 / 21.5 / 22).
  const decimals = Math.max(0, -Math.floor(Math.log10(step)))
  return { lo, hi, ticks, decimals }
}

function formatTime(ts: number, spanSeconds: number) {
  const d = new Date(ts * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return spanSeconds <= 48 * 3600
    ? `${pad(d.getHours())}:${pad(d.getMinutes())}`
    : `${pad(d.getDate())}.${pad(d.getMonth() + 1)}`
}

function formatStamp(ts: number) {
  const d = new Date(ts * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function LineChart({ series, unit, start, end, gapSeconds, decimals }: Props) {
  const [cursor, setCursor] = useState<number | null>(null)

  const active = series.filter(s => s.points.length > 0)
  const span = Math.max(1, end - start)

  const scale = useMemo(() => {
    const values = active.flatMap(s => s.points.map(p => p[1]))
    if (values.length === 0) return null
    const nice = niceTicks(Math.min(...values), Math.max(...values))
    const { lo, hi } = nice
    const x = (ts: number) => PAD.left + ((ts - start) / span) * PLOT_W
    const y = (v: number) => PAD.top + (1 - (v - lo) / (hi - lo || 1)) * PLOT_H
    return { x, y, ticks: nice.ticks, tickDecimals: nice.decimals }
  }, [active, start, span])

  if (!scale) {
    return (
      <div className="card-dashed" style={{ padding: 24, textAlign: 'center', fontSize: 13 }}>
        No readings in this range
      </div>
    )
  }

  const xTicks = [0, 0.25, 0.5, 0.75, 1].map(f => start + f * span)

  // One direct label per series: the latest value, or the value under the
  // cursor while scrubbing. No separate legend — the pills carry the colours.
  const readout = active.map(s => {
    if (cursor === null) {
      const last = s.points[s.points.length - 1]
      return { ...s, at: last[0], value: last[1] as number | null }
    }
    let best = s.points[0]
    for (const p of s.points) {
      if (Math.abs(p[0] - cursor) < Math.abs(best[0] - cursor)) best = p
    }
    return { ...s, at: best[0], value: Math.abs(best[0] - cursor) <= gapSeconds ? best[1] : null }
  })

  // Labels share a y with their line, then get pushed apart just enough to stay
  // legible when two rooms sit within a fraction of a degree of each other.
  const labels = readout
    .flatMap(s => s.value === null ? [] : [{ ...s, value: s.value, y: scale.y(s.value) }])
    .sort((a, b) => a.y - b.y)
  labels.forEach((l, i) => {
    if (i > 0 && l.y - labels[i - 1].y < LABEL_GAP) l.y = labels[i - 1].y + LABEL_GAP
  })

  // The cursor is sticky: a tap places it and it stays put, so the value can be
  // read after lifting your thumb off the chart. Tapping outside the plot, or
  // on the marker's own time label, clears it.
  const onPointer = (e: PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const fx = ((e.clientX - rect.left) / rect.width) * W
    if (fx < PAD.left || fx > W - PAD.right) return setCursor(null)
    setCursor(start + ((fx - PAD.left) / PLOT_W) * span)
  }

  const onPointerDown = (e: PointerEvent<SVGSVGElement>) => {
    // Capture so dragging past the edge keeps updating instead of dropping out.
    e.currentTarget.setPointerCapture?.(e.pointerId)
    onPointer(e)
  }

  return (
    <div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: '100%', display: 'block', touchAction: 'pan-y' }}
        onPointerDown={onPointerDown}
        onPointerMove={e => { if (e.buttons) onPointer(e) }}
      >
        {scale.ticks.map(v => (
          <g key={v}>
            <line
              x1={PAD.left} x2={W - PAD.right} y1={scale.y(v)} y2={scale.y(v)}
              stroke="var(--border)" strokeWidth={1}
            />
            <text
              x={PAD.left - 8} y={scale.y(v) + 4} textAnchor="end"
              fontSize={TICK_SIZE} fill="var(--text-muted)"
            >
              {v.toFixed(scale.tickDecimals)}
            </text>
          </g>
        ))}

        {xTicks.map((ts, i) => (
          <text
            key={ts} x={scale.x(ts)} y={H - 8}
            textAnchor={i === 0 ? 'start' : i === xTicks.length - 1 ? 'end' : 'middle'}
            fontSize={TICK_SIZE} fill="var(--text-muted)"
          >
            {formatTime(ts, span)}
          </text>
        ))}

        {active.map(s => {
          // A lone reading has no segment to stroke, so draw it as a dot —
          // otherwise a freshly deployed chart looks empty.
          if (s.points.length === 1) {
            return (
              <circle
                key={s.key} cx={scale.x(s.points[0][0])} cy={scale.y(s.points[0][1])}
                r={3} fill={s.color}
              />
            )
          }
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
          <g>
            <line
              x1={scale.x(cursor)} x2={scale.x(cursor)}
              y1={PAD.top} y2={PAD.top + PLOT_H}
              stroke="var(--text-muted)" strokeWidth={1} strokeDasharray="3 3"
            />
            {/* When you are reading a past value, say which moment it is. */}
            <text
              x={Math.min(Math.max(scale.x(cursor), PAD.left + 34), W - PAD.right - 34)}
              y={PAD.top - 9} textAnchor="middle"
              fontSize={TICK_SIZE} fontWeight={500} fill="var(--text-secondary)"
            >
              {formatStamp(cursor)}
            </text>
          </g>
        )}
        {cursor !== null && labels.map(s => (
          <circle
            key={s.key} cx={scale.x(s.at)} cy={scale.y(s.value)} r={4}
            fill={s.color} stroke="var(--bg-card)" strokeWidth={2}
          />
        ))}

        {/* Direct labels instead of a legend block: the value sits at the end
            of its own line, nudged apart only when two would overlap. */}
        {labels.map(s => (
          <text
            key={s.key} x={W - PAD.right + 6} y={s.y + 4}
            fontSize={LABEL_SIZE} fontWeight={500} fill={s.color}
          >
            {s.value.toFixed(decimals)}{unit}
          </text>
        ))}
      </svg>
    </div>
  )
}
