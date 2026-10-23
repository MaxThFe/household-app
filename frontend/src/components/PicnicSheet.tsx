import { useCallback, useEffect, useState } from 'react'
import {
  api,
  PicnicMapping,
  PicnicOrderLine,
  PicnicOrderPreview,
  PicnicProduct,
  PicnicQuestion,
  PicnicStatus,
} from '../api/client'
import { Modal } from './Modal'

// Prepare (map what is new) -> questions (if any) -> review counts -> cart.
type Step = 'prepare' | 'questions' | 'review' | 'done'

function euros(cents: number | null): string {
  return cents == null ? '' : `€${(cents / 100).toFixed(2).replace('.', ',')}`
}

function ProductRow({ product, onClick, right }: {
  product: PicnicProduct
  onClick?: () => void
  right?: React.ReactNode
}) {
  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0',
        cursor: onClick ? 'pointer' : undefined,
      }}
    >
      {product.image_url
        ? <img src={product.image_url} alt="" width={40} height={40} style={{ objectFit: 'contain', borderRadius: 6 }} />
        : <div style={{ width: 40, height: 40 }} />}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14 }}>{product.name}</div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
          {[product.unit_quantity, euros(product.price)].filter(Boolean).join(' · ')}
        </div>
      </div>
      {right}
    </div>
  )
}

function QuestionCard({ question, onAnswered }: { question: PicnicQuestion; onAnswered: () => void }) {
  const [text, setText] = useState('')
  const [recipeOnly, setRecipeOnly] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function answer(data: { product_id?: string; text?: string; skip?: boolean }) {
    setBusy(true)
    setError('')
    try {
      await api.picnic.answer(question.id, { ...data, scope: recipeOnly ? 'recipe' : 'global' })
      onAnswered()
    } catch (e) {
      setError(String(e))
      setBusy(false)
    }
  }

  return (
    <div className="card" style={{ opacity: busy ? 0.5 : 1 }}>
      <div style={{ fontSize: 15, fontWeight: 500, textTransform: 'capitalize' }}>{question.item_key}</div>
      {question.recipe_names && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>for {question.recipe_names}</div>
      )}
      <p style={{ fontSize: 14, margin: '8px 0' }}>{question.question}</p>
      {question.candidates.map(c => (
        <ProductRow key={c.product_id} product={c} onClick={busy ? undefined : () => answer({ product_id: c.product_id })} />
      ))}
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <input
          className="form-input"
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && text.trim()) answer({ text }) }}
          placeholder="Or say what you mean…"
          disabled={busy}
        />
        <button className="pill pill-active" disabled={busy || !text.trim()} onClick={() => answer({ text })}>
          Send
        </button>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10, fontSize: 13 }}>
        {question.recipe_id ? (
          <label style={{ display: 'flex', gap: 6, alignItems: 'center', color: 'var(--text-secondary)' }}>
            <input type="checkbox" checked={recipeOnly} onChange={e => setRecipeOnly(e.target.checked)} />
            Only for {question.recipe_names}
          </label>
        ) : <span />}
        <button style={{ color: 'var(--text-muted)' }} disabled={busy} onClick={() => answer({ skip: true })}>
          Not from Picnic
        </button>
      </div>
      {error && <p style={{ color: 'var(--accent-red)', fontSize: 12, marginTop: 6 }}>{error}</p>}
    </div>
  )
}

function OrderTab() {
  const [step, setStep] = useState<Step>('prepare')
  const [status, setStatus] = useState<PicnicStatus | null>(null)
  const [questions, setQuestions] = useState<PicnicQuestion[]>([])
  const [preview, setPreview] = useState<PicnicOrderPreview | null>(null)
  const [lines, setLines] = useState<PicnicOrderLine[]>([])
  const [failed, setFailed] = useState<string[]>([])
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')

  const toQuestionsOrReview = useCallback(async () => {
    const open = await api.picnic.questions()
    setQuestions(open)
    if (open.length > 0) {
      setStep('questions')
      return
    }
    const p = await api.picnic.preview()
    setPreview(p)
    setLines(p.lines)
    setStep('review')
  }, [])

  // Map whatever is new on the list, then poll until the job is through.
  useEffect(() => {
    let cancelled = false
    async function run() {
      try {
        let s = await api.picnic.status()
        if (!s.llm_configured || !s.any_connected) {
          setStatus(s)
          return
        }
        if (s.pending_items > 0) s = await api.picnic.resolve()
        while (s.running && !cancelled) {
          setStatus(s)
          await new Promise(r => setTimeout(r, 1500))
          s = await api.picnic.status()
        }
        if (cancelled) return
        setStatus(s)
        if (s.error) return
        await toQuestionsOrReview()
      } catch (e) {
        if (!cancelled) setError(String(e))
      }
    }
    run()
    return () => { cancelled = true }
  }, [toQuestionsOrReview])

  async function sendToCart() {
    setSending(true)
    setError('')
    try {
      const results = await api.picnic.order(lines.map(l => ({ product_id: l.product_id, count: l.count })))
      const names = Object.fromEntries(lines.map(l => [l.product_id, l.name]))
      setFailed(results.filter(r => !r.ok).map(r => names[r.product_id] ?? r.product_id))
      setStep('done')
    } catch (e) {
      setError(String(e))
    }
    setSending(false)
  }

  function setCount(productId: string, delta: number) {
    setLines(prev => prev.map(l => l.product_id === productId ? { ...l, count: Math.max(0, l.count + delta) } : l))
  }

  if (error) return <p style={{ color: 'var(--accent-red)', fontSize: 14 }}>{error}</p>

  if (step === 'prepare') {
    if (status && !status.llm_configured) return <p>Set HT_OPENAI_API_KEY in backend/.env to map items.</p>
    if (status && !status.any_connected) return <p>Nobody is logged in to Picnic yet — run <code>python picnic_setup.py</code> on the server.</p>
    if (status?.error) return <p style={{ color: 'var(--accent-red)' }}>{status.error}</p>
    return (
      <div className="loading">
        {status?.running && status.total > 0
          ? `Matching new items to Picnic… ${status.done}/${status.total}`
          : 'Checking the list…'}
      </div>
    )
  }

  if (step === 'questions') {
    return (
      <>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12 }}>
          A few items need your call. Answers are remembered.
        </p>
        {questions.map(q => <QuestionCard key={q.id} question={q} onAnswered={toQuestionsOrReview} />)}
        <button className="btn-secondary" style={{ width: '100%', marginTop: 8 }} onClick={async () => {
          const p = await api.picnic.preview()
          setPreview(p)
          setLines(p.lines)
          setStep('review')
        }}>
          Skip for now
        </button>
      </>
    )
  }

  if (step === 'done') {
    return (
      <div className="empty-state">
        <p style={{ fontSize: 32, marginBottom: 12 }}>🧺</p>
        <p>Added to your Picnic cart. Check out in the Picnic app.</p>
        {failed.length > 0 && (
          <p style={{ color: 'var(--accent-red)', marginTop: 8 }}>Could not add: {failed.join(', ')}</p>
        )}
      </div>
    )
  }

  const total = lines.reduce((sum, l) => sum + (l.price ?? 0) * l.count, 0)
  return (
    <>
      {lines.map(l => (
        <div key={l.product_id}>
          <ProductRow
            product={l}
            right={
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <button className="pill pill-inactive" onClick={() => setCount(l.product_id, -1)}>−</button>
                <span style={{ minWidth: 16, textAlign: 'center', opacity: l.count ? 1 : 0.4 }}>{l.count}</span>
                <button className="pill pill-inactive" onClick={() => setCount(l.product_id, 1)}>+</button>
              </div>
            }
          />
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: -6, marginLeft: 50 }}>
            {l.items.join(', ')}
          </div>
        </div>
      ))}
      {lines.length === 0 && <p style={{ color: 'var(--text-secondary)' }}>Nothing to order from Picnic.</p>}
      {preview && preview.unmapped.length > 0 && (
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 12 }}>
          Not matched yet: {preview.unmapped.join(', ')}
        </p>
      )}
      {preview && preview.skipped.length > 0 && (
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
          Not from Picnic: {preview.skipped.join(', ')}
        </p>
      )}
      <button
        className="btn-primary"
        style={{ width: '100%', marginTop: 16 }}
        disabled={sending || lines.every(l => l.count === 0)}
        onClick={sendToCart}
      >
        {sending ? 'Adding…' : `Add to Picnic cart${total ? ` · ${euros(total)}` : ''}`}
      </button>
    </>
  )
}

function MappingsTab() {
  const [mappings, setMappings] = useState<PicnicMapping[] | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = useCallback(() => { api.picnic.mappings().then(setMappings) }, [])
  useEffect(load, [load])

  async function act(id: number, action: (id: number) => Promise<unknown>) {
    setBusyId(id)
    try { await action(id) } finally {
      setBusyId(null)
      load()
    }
  }

  if (!mappings) return <div className="loading">Loading…</div>
  if (mappings.length === 0) return <p style={{ color: 'var(--text-secondary)' }}>Nothing matched yet.</p>
  return (
    <>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8 }}>
        "Ask again" puts the item back as a question. A new question shows up under Order.
      </p>
      {mappings.map(m => (
        <div key={m.id} className="card" style={{ opacity: busyId === m.id ? 0.5 : 1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <span style={{ fontWeight: 500, textTransform: 'capitalize' }}>{m.item_key}</span>
            {m.recipe_name && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>only {m.recipe_name}</span>}
          </div>
          {m.product
            ? <ProductRow product={m.product} />
            : <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '6px 0' }}>Not from Picnic</p>}
          <div style={{ display: 'flex', gap: 12, fontSize: 13 }}>
            <button style={{ color: 'var(--text-secondary)' }} disabled={busyId !== null} onClick={() => act(m.id, api.picnic.reask)}>
              Ask again
            </button>
            <button style={{ color: 'var(--accent-red)' }} disabled={busyId !== null} onClick={() => act(m.id, api.picnic.forget)}>
              Forget
            </button>
          </div>
        </div>
      ))}
    </>
  )
}

export function PicnicSheet({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<'order' | 'mappings'>('order')
  return (
    <Modal title="Order via Picnic" onClose={onClose}>
      <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
        {(['order', 'mappings'] as const).map(t => (
          <button key={t} className={`pill ${tab === t ? 'pill-active' : 'pill-inactive'}`} onClick={() => setTab(t)}>
            {t === 'order' ? 'Order' : 'Matched items'}
          </button>
        ))}
      </div>
      {tab === 'order' ? <OrderTab /> : <MappingsTab />}
    </Modal>
  )
}
