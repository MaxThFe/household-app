import { useRef, useState } from 'react'
import { api, MarketInfo, SectionInfo } from '../api/client'
import { Modal } from './Modal'

interface Props {
  market: MarketInfo
  sections: SectionInfo[]
  order: string[]
  onClose: () => void
  onSaved: () => void
}

export function SectionOrderSheet({ market, sections, order, onClose, onSaved }: Props) {
  const [slugs, setSlugs] = useState<string[]>(order)
  const [saving, setSaving] = useState(false)

  // Drag state: index being dragged, where it would land, and the live offset
  const [dragIdx, setDragIdx] = useState<number | null>(null)
  const [overIdx, setOverIdx] = useState<number | null>(null)
  const [offsetY, setOffsetY] = useState(0)
  const startY = useRef(0)
  const rowHeight = useRef(44)
  const rowRefs = useRef<(HTMLDivElement | null)[]>([])

  const byslug = new Map(sections.map(s => [s.slug, s]))

  function handlePointerDown(e: React.PointerEvent, index: number) {
    // Pointer events cover mouse, pen and touch with one code path
    e.preventDefault()
    e.currentTarget.setPointerCapture(e.pointerId)
    const row = rowRefs.current[index]
    if (row) rowHeight.current = row.getBoundingClientRect().height
    startY.current = e.clientY
    setDragIdx(index)
    setOverIdx(index)
    setOffsetY(0)
  }

  function handlePointerMove(e: React.PointerEvent) {
    if (dragIdx === null) return
    const dy = e.clientY - startY.current
    setOffsetY(dy)
    const steps = Math.round(dy / rowHeight.current)
    const target = Math.max(0, Math.min(slugs.length - 1, dragIdx + steps))
    setOverIdx(target)
  }

  function handlePointerUp() {
    if (dragIdx !== null && overIdx !== null && overIdx !== dragIdx) {
      setSlugs(prev => {
        const next = [...prev]
        const [moved] = next.splice(dragIdx, 1)
        next.splice(overIdx, 0, moved)
        return next
      })
    }
    setDragIdx(null)
    setOverIdx(null)
    setOffsetY(0)
  }

  // Rows between the grabbed row and its target slide out of the way
  function shiftFor(index: number): number {
    if (dragIdx === null || overIdx === null) return 0
    if (index === dragIdx) return offsetY
    if (dragIdx < overIdx && index > dragIdx && index <= overIdx) return -rowHeight.current
    if (dragIdx > overIdx && index >= overIdx && index < dragIdx) return rowHeight.current
    return 0
  }

  async function handleSave() {
    setSaving(true)
    try {
      await api.shopping.setSectionOrder(market.slug, slugs)
      onSaved()
      onClose()
    } catch {
      setSaving(false)
    }
  }

  return (
    <Modal
      title={`Aisle order — ${market.label}`}
      onClose={onClose}
      footer={
        <button className="btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </button>
      }
    >
      <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
        Drag the sections into the order you walk them at {market.label}.
      </p>
      <div className="shopping-list-card">
        {slugs.map((slug, i) => {
          const section = byslug.get(slug)
          if (!section) return null
          const dragging = dragIdx === i
          return (
            <div
              key={slug}
              ref={el => { rowRefs.current[i] = el }}
              className={`shopping-item-row section-order-row${dragging ? ' dragging' : ''}`}
              style={{ transform: `translateY(${shiftFor(i)}px)` }}
            >
              <span
                className="drag-handle"
                onPointerDown={e => handlePointerDown(e, i)}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onPointerCancel={handlePointerUp}
              >
                <GripIcon />
              </span>
              <span style={{ flex: 1, fontSize: 14 }}>{section.label}</span>
            </div>
          )
        })}
      </div>
    </Modal>
  )
}

function GripIcon() {
  return (
    <svg width="12" height="16" viewBox="0 0 12 16" fill="currentColor">
      <circle cx="4" cy="4" r="1.3" />
      <circle cx="8" cy="4" r="1.3" />
      <circle cx="4" cy="8" r="1.3" />
      <circle cx="8" cy="8" r="1.3" />
      <circle cx="4" cy="12" r="1.3" />
      <circle cx="8" cy="12" r="1.3" />
    </svg>
  )
}
