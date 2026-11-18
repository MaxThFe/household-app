import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  api,
  FailingAccount,
  GroceryStore,
  PurchaseDetail,
  PurchaseSummary,
  SpendingMonth,
  SpendingStats,
  Stat,
} from '../api/client'
import { useAuth } from '../App'
import { Modal } from '../components/Modal'

// Colour identifies the store, in a fixed order that is also the stacking
// order from the baseline up. Validated as a categorical set on white
// (lightness band, chroma, CVD and contrast all pass).
const STORES: { key: GroceryStore, label: string, color: string }[] = [
  { key: 'picnic', label: 'Picnic', color: '#B8431F' },
  { key: 'ah', label: 'Albert Heijn', color: '#1F6FB8' },
  { key: 'lidl', label: 'Lidl', color: '#8A6D00' },
]
const STORE_BY_KEY = Object.fromEntries(STORES.map(s => [s.key, s]))

const euro = new Intl.NumberFormat('nl-NL', { style: 'currency', currency: 'EUR' })
const euroRound = new Intl.NumberFormat('nl-NL', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 })
const money = (cents: number) => euro.format(cents / 100)

function monthLabel(month: string, style: 'short' | 'long' = 'short') {
  const [y, m] = month.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleDateString('en-GB', style === 'short'
    ? { month: 'short' }
    : { month: 'long', year: 'numeric' })
}

/** Every month from the first one to this one, so empty months show as gaps. */
function monthRange(first: string): string[] {
  const now = new Date()
  const last = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  const out: string[] = []
  let [y, m] = first.split('-').map(Number)
  for (let guard = 0; guard < 240; guard++) {
    const key = `${y}-${String(m).padStart(2, '0')}`
    out.push(key)
    if (key >= last) break
    m += 1
    if (m > 12) { m = 1; y += 1 }
  }
  return out
}

export default function Spending() {
  const navigate = useNavigate()
  const { config } = useAuth()
  const [params, setParams] = useSearchParams()
  const who = params.get('who') ?? ''
  // 'stats' is a tab of its own, not a person.
  const person = who && who !== 'stats' ? who : undefined

  const [since, setSince] = useState('')
  const [months, setMonths] = useState<SpendingMonth[]>([])
  const [purchases, setPurchases] = useState<PurchaseSummary[]>([])
  const [open, setOpen] = useState<PurchaseDetail | null>(null)
  // Bumped after a delete, to load the totals and receipts again.
  const [reload, setReload] = useState(0)
  const [failing, setFailing] = useState<FailingAccount[] | null>(null)

  useEffect(() => { api.spending.health().then(setFailing).catch(() => {}) }, [])

  useEffect(() => {
    api.spending.months(person)
      .then(r => { setSince(r.since); setMonths(r.months) })
      .catch(() => {})
  }, [person, reload])

  const range = useMemo(() => (since ? monthRange(since.slice(0, 7)) : []), [since])
  const selected = params.get('month') ?? range[range.length - 1] ?? ''

  useEffect(() => {
    if (!selected) return
    api.spending.purchases(selected, person).then(setPurchases).catch(() => {})
  }, [selected, person, months])

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  // month -> store -> cents
  const byMonth = useMemo(() => {
    const map = new Map<string, Map<GroceryStore, number>>()
    months.forEach(m => {
      const row = map.get(m.month) ?? new Map()
      row.set(m.store, m.total_cents)
      map.set(m.month, row)
    })
    return map
  }, [months])

  const monthTotal = (month: string) =>
    [...(byMonth.get(month)?.values() ?? [])].reduce((a, b) => a + b, 0)

  const people = config ? [config.user1_name, config.user2_name] : []
  const filters: [string, string][] = [['', 'Everyone'], ...people.map(p => [p, p] as [string, string]), ['stats', 'Stats']]

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button onClick={() => navigate('/')} style={{ display: 'flex', padding: 4, marginLeft: -4, color: 'var(--text-secondary)' }}>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M12 4l-6 6 6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <p style={{ fontSize: 22, fontWeight: 500 }}>Groceries</p>
        </div>
      </div>

      <div style={{ padding: '16px 20px' }}>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
          {filters.map(([key, label]) => (
            <button
              key={key || 'all'}
              className={`pill ${who === key ? 'pill-active' : 'pill-inactive'}`}
              onClick={() => update('who', key)}
            >
              {label}
            </button>
          ))}
        </div>

        {who === 'stats' ? <Stats /> : (
          <>
          {selected && (
            <div style={{ marginBottom: 16 }}>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{monthLabel(selected, 'long')}</p>
              <p style={{ fontSize: 30, fontWeight: 500, marginTop: 2 }}>{money(monthTotal(selected))}</p>
            </div>
          )}

          {range.length > 0 && (
            <div className="card" style={{ padding: '12px 10px' }}>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', margin: '0 6px 8px' }}>
                {STORES.map(s => (
                  <span key={s.key} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-secondary)' }}>
                    <span style={{ width: 10, height: 10, borderRadius: 3, background: s.color }} />
                    {s.label}
                  </span>
                ))}
              </div>
              <MonthBars range={range} byMonth={byMonth} selected={selected} onSelect={m => update('month', m)} />
            </div>
          )}

          {selected && (
            <div style={{ margin: '20px 0' }}>
              <p className="section-label">By store</p>
              <div className="list-card">
                {STORES.map(s => {
                  const cents = byMonth.get(selected)?.get(s.key) ?? 0
                  const count = months.find(m => m.month === selected && m.store === s.key)?.purchases ?? 0
                  return (
                    <div key={s.key} className="list-row" style={{ fontSize: 14 }}>
                      <span style={{ width: 10, height: 10, borderRadius: 3, background: s.color, flexShrink: 0 }} />
                      <span style={{ flex: 1 }}>{s.label}</span>
                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                        {count} {count === 1 ? 'receipt' : 'receipts'}
                      </span>
                      <span style={{ width: 84, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{money(cents)}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {purchases.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <p className="section-label">Receipts</p>
              <div className="list-card">
                {purchases.map(p => (
                  <div
                    key={p.id}
                    className="list-row"
                    style={{ cursor: 'pointer', fontSize: 14 }}
                    onClick={() => api.spending.purchase(p.id).then(setOpen).catch(() => {})}
                  >
                    <span style={{ width: 10, height: 10, borderRadius: 3, background: STORE_BY_KEY[p.store].color, flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p>{STORE_BY_KEY[p.store].label}</p>
                      <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                        {new Date(p.purchased_at).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })}
                        {' · '}{p.person}{' · '}{p.item_count} {p.item_count === 1 ? 'item' : 'items'}
                      </p>
                    </div>
                    <span style={{ fontVariantNumeric: 'tabular-nums' }}>{money(p.total_cents)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          </>
        )}

        {failing && (
          <div style={{ display: 'flex', justifyContent: 'center', marginTop: 8 }}>
            <span className="pill" style={{ gap: 6, cursor: 'default', background: 'var(--bg-inactive)', color: '#6B5D4D' }}>
              <span style={{
                width: 8, height: 8, borderRadius: 4,
                background: failing.length ? 'var(--accent-red)' : 'var(--accent-green)',
              }} />
              {failing.length
                ? `Sync not working: ${failing.map(f => `${STORE_BY_KEY[f.store].label} (${f.person})`).join(', ')}`
                : 'Sync working'}
            </span>
          </div>
        )}
      </div>

      {open && (
        <Modal
          title={`${STORE_BY_KEY[open.store].label} · ${new Date(open.purchased_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}`}
          onClose={() => setOpen(null)}
        >
          <ReceiptItems purchase={open} onDeleted={() => { setOpen(null); setReload(r => r + 1) }} />
        </Modal>
      )}
    </div>
  )
}

// --- the chart ----------------------------------------------------------------

const W = 440
const H = 190
const PAD = { top: 22, right: 8, bottom: 26, left: 52 }
const PLOT_W = W - PAD.left - PAD.right
const PLOT_H = H - PAD.top - PAD.bottom

function niceMax(value: number): { max: number, step: number } {
  if (value <= 0) return { max: 100, step: 50 }
  const rough = value / 3
  const mag = Math.pow(10, Math.floor(Math.log10(rough)))
  const norm = rough / mag
  const step = (norm > 5 ? 10 : norm > 2 ? 5 : norm > 1 ? 2 : 1) * mag
  return { max: Math.ceil(value / step) * step, step }
}

/** A bar segment with its top corners rounded: the data end of the stack. */
function topRounded(x: number, y: number, w: number, h: number, r: number) {
  r = Math.min(r, h, w / 2)
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`
}

function MonthBars({ range, byMonth, selected, onSelect }: {
  range: string[]
  byMonth: Map<string, Map<GroceryStore, number>>
  selected: string
  onSelect: (month: string) => void
}) {
  const totals = range.map(m => [...(byMonth.get(m)?.values() ?? [])].reduce((a, b) => a + b, 0) / 100)
  const { max, step } = niceMax(Math.max(...totals, 0))
  const ticks = Array.from({ length: Math.round(max / step) + 1 }, (_, i) => i * step)
  const slot = PLOT_W / range.length
  const barW = Math.min(34, slot * 0.62)
  const y = (euros: number) => PAD.top + PLOT_H - (euros / max) * PLOT_H
  const GAP = 2  // surface gap between stacked segments

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block', touchAction: 'manipulation' }} role="img"
      aria-label="Grocery spending per month, stacked by store">
      {ticks.map(t => (
        <g key={t}>
          <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} stroke="#EDE6DC" strokeWidth={t === 0 ? 1 : 0.5} />
          <text x={PAD.left - 6} y={y(t) + 4} textAnchor="end" fontSize={12} fill="#8B7D6B">
            {euroRound.format(t)}
          </text>
        </g>
      ))}
      {range.map((month, i) => {
        const cx = PAD.left + slot * (i + 0.5)
        const x = cx - barW / 2
        const isSelected = month === selected
        const segments = STORES
          .map(s => ({ store: s, euros: (byMonth.get(month)?.get(s.key) ?? 0) / 100 }))
          .filter(s => s.euros > 0)
        let base = 0
        return (
          <g key={month} onClick={() => onSelect(month)} style={{ cursor: 'pointer' }}
            opacity={isSelected ? 1 : 0.55}>
            {/* Hit target: the whole column, not just the bar. */}
            <rect x={PAD.left + slot * i} y={PAD.top} width={slot} height={PLOT_H + PAD.bottom} fill="transparent" />
            {segments.map((seg, j) => {
              const top = y(base + seg.euros)
              const bottom = y(base)
              base += seg.euros
              const h = Math.max(bottom - top - (j > 0 ? GAP : 0), 1)
              const last = j === segments.length - 1
              return last
                ? <path key={seg.store.key} d={topRounded(x, top, barW, h, 4)} fill={seg.store.color} />
                : <rect key={seg.store.key} x={x} y={top} width={barW} height={h} fill={seg.store.color} />
            })}
            {isSelected && totals[i] > 0 && (
              <text x={cx} y={y(totals[i]) - 6} textAnchor="middle" fontSize={12} fontWeight={500} fill="#4A3F35">
                {euroRound.format(totals[i])}
              </text>
            )}
            <text x={cx} y={H - 8} textAnchor="middle" fontSize={12}
              fill={isSelected ? '#4A3F35' : '#8B7D6B'} fontWeight={isSelected ? 500 : 400}>
              {monthLabel(month)}
            </text>
            <title>
              {`${monthLabel(month, 'long')}: ${euro.format(totals[i])}` +
                segments.map(s => `\n${s.store.label}: ${euro.format(s.euros)}`).join('')}
            </title>
          </g>
        )
      })}
    </svg>
  )
}

// --- the stats tab ---------------------------------------------------------------

/** Household averages over the complete months, each split per person. */
function Stats() {
  const [stats, setStats] = useState<SpendingStats | null>(null)
  useEffect(() => { api.spending.stats().then(setStats).catch(() => {}) }, [])
  if (!stats) return null
  if (stats.per_month_cents.total === null) {
    return <div className="card-dashed" style={{ fontSize: 13 }}>No complete month yet</div>
  }
  const runs = (n: number) => n.toLocaleString('nl-NL', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
  const sections: [string, Stat, (n: number) => string][] = [
    ['Avg monthly', stats.per_month_cents, money],
    ['Avg weekly', stats.per_week_cents, money],
    ['Runs per week', stats.runs_per_week, runs],
    ['Avg per run', stats.per_run_cents, money],
  ]
  return (
    <div className="list-card" style={{ marginBottom: 20 }}>
      {sections.flatMap(([label, stat, format]) => [
        <div key={label} className="list-row" style={{ fontSize: 14 }}>
          <span style={{ flex: 1 }}>{label}</span>
          <span style={{ fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>
            {stat.total !== null ? format(stat.total) : '–'}
          </span>
        </div>,
        ...Object.entries(stat.by_person).map(([person, value]) => (
          <div key={`${label}:${person}`} className="list-row" style={{ fontSize: 13, paddingLeft: 32, color: 'var(--text-secondary)' }}>
            <span style={{ flex: 1 }}>{person}</span>
            <span style={{ fontVariantNumeric: 'tabular-nums' }}>{format(value)}</span>
          </div>
        )),
      ])}
    </div>
  )
}

function ReceiptItems({ purchase, onDeleted }: { purchase: PurchaseDetail, onDeleted: () => void }) {
  const [deleting, setDeleting] = useState(false)

  async function handleDelete() {
    if (!confirm('Delete this receipt?')) return
    setDeleting(true)
    try {
      await api.spending.deletePurchase(purchase.id)
      onDeleted()
    } catch {
      setDeleting(false)
    }
  }

  return (
    <div>
      {purchase.items.map(item => (
        <div key={item.line_no} style={{ display: 'flex', gap: 8, padding: '6px 0', borderBottom: '0.5px solid var(--border)', fontSize: 14 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p>{item.name}</p>
            {item.discount_cents > 0 && (
              <p style={{ fontSize: 12, color: 'var(--accent-green)' }}>−{money(item.discount_cents)} discount</p>
            )}
          </div>
          <span style={{ fontVariantNumeric: 'tabular-nums' }}>
            {item.amount_cents !== null ? money(item.amount_cents - item.discount_cents) : ''}
          </span>
        </div>
      ))}
      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0 0', fontSize: 15, fontWeight: 500 }}>
        <span>Total paid</span>
        <span style={{ fontVariantNumeric: 'tabular-nums' }}>{money(purchase.total_cents)}</span>
      </div>
      <button className="btn-danger" style={{ width: '100%', marginTop: 20 }} onClick={handleDelete} disabled={deleting}>
        Delete receipt
      </button>
    </div>
  )
}
