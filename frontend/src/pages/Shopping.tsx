import { useState, useEffect, useCallback, useRef } from 'react'
import { api, ShoppingItem, ShoppingList } from '../api/client'
import { Modal } from '../components/Modal'
import { Toast } from '../components/Toast'

// --- Add item modal ---
interface AddItemModalProps {
  onClose: () => void
  onSaved: () => void
}

function AddItemModal({ onClose, onSaved, existingCategories }: AddItemModalProps & { existingCategories: string[] }) {
  const [name, setName] = useState('')
  const [quantity, setQuantity] = useState('')
  const [unit, setUnit] = useState('')
  const [store, setStore] = useState('supermarket')
  const [customStore, setCustomStore] = useState('')
  const [showCustomInput, setShowCustomInput] = useState(false)
  const [saving, setSaving] = useState(false)

  const defaultCategories = ['supermarket', 'household']
  const customCategories = existingCategories.filter(c => !defaultCategories.includes(c))
  const allPills = [...defaultCategories, ...customCategories]

  async function handleSave() {
    if (!name.trim()) return
    const finalStore = showCustomInput ? customStore.trim().toLowerCase() : store
    if (!finalStore) return
    setSaving(true)
    try {
      await api.shopping.add({
        name: name.trim(),
        quantity: quantity ? parseFloat(quantity) : undefined,
        unit: unit || undefined,
        store: finalStore,
      })
      onSaved()
      onClose()
    } catch {
      setSaving(false)
    }
  }

  return (
    <Modal
      title="Add item"
      onClose={onClose}
      footer={
        <button className="btn-primary" onClick={handleSave} disabled={saving || !name.trim() || (showCustomInput && !customStore.trim())}>
          {saving ? 'Saving…' : 'Add'}
        </button>
      }
    >
      <div className="form-group">
        <label className="form-label">Item name</label>
        <input className="form-input" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Garlic" autoFocus />
      </div>
      <div style={{ display: 'flex', gap: 12 }}>
        <div className="form-group" style={{ flex: 1 }}>
          <label className="form-label">Quantity</label>
          <input className="form-input" type="number" value={quantity} onChange={e => setQuantity(e.target.value)} placeholder="–" />
        </div>
        <div className="form-group" style={{ flex: 1 }}>
          <label className="form-label">Unit</label>
          <input className="form-input" value={unit} onChange={e => setUnit(e.target.value)} placeholder="g, ml, pcs…" />
        </div>
      </div>
      <div className="form-group">
        <label className="form-label">Category</label>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {allPills.map(s => (
            <button
              key={s}
              className={`pill ${!showCustomInput && store === s ? 'pill-active' : 'pill-inactive'}`}
              onClick={() => { setStore(s); setShowCustomInput(false) }}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
          <button
            className={`pill ${showCustomInput ? 'pill-active' : 'pill-inactive'}`}
            onClick={() => setShowCustomInput(true)}
          >
            + Custom
          </button>
        </div>
        {showCustomInput && (
          <input
            className="form-input"
            style={{ marginTop: 8 }}
            value={customStore}
            onChange={e => setCustomStore(e.target.value)}
            placeholder="Category name"
            autoFocus
          />
        )}
      </div>
    </Modal>
  )
}

// --- Shopping item row ---
interface ShoppingRowProps {
  item: ShoppingItem
  onCheck: (item: ShoppingItem) => void
  pendingIds: Set<number>
}

function ShoppingRow({ item, onCheck, pendingIds }: ShoppingRowProps) {
  const isPending = pendingIds.has(item.id)

  return (
    <div className="shopping-item-row" style={{ opacity: isPending ? 0.4 : 1, transition: 'opacity 0.2s' }}>
      <input
        type="checkbox"
        className="shopping-checkbox"
        checked={isPending}
        onChange={() => onCheck(item)}
      />
      <div style={{ flex: 1 }}>
        <p style={{ fontSize: 14, color: 'var(--text-primary)' }}>{item.name}</p>
        {item.source_names && (
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>{item.source_names}</p>
        )}
        {item.is_manual === 1 && !item.source_names && (
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>manually added</p>
        )}
      </div>
      {item.quantity != null && (
        <p style={{ fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
          {item.quantity}{item.unit ? ` ${item.unit}` : ''}
        </p>
      )}
    </div>
  )
}

// --- Section ---
function Section({ title, items, onCheck, pendingIds }: { title: string; items: ShoppingItem[]; onCheck: (item: ShoppingItem) => void; pendingIds: Set<number> }) {
  if (items.length === 0) return null
  return (
    <div className="shopping-group">
      <div className="shopping-group-header">
        <span>{title}</span>
        <span>{items.length} {items.length === 1 ? 'item' : 'items'}</span>
      </div>
      <div className="shopping-list-card">
        {items.map(item => (
          <ShoppingRow key={item.id} item={item} onCheck={onCheck} pendingIds={pendingIds} />
        ))}
      </div>
    </div>
  )
}

// --- Main shopping page ---
export default function Shopping() {
  const [list, setList] = useState<ShoppingList>({ categories: {} })
  const [loading, setLoading] = useState(true)
  const [showAddModal, setShowAddModal] = useState(false)
  const [pendingIds, setPendingIds] = useState<Set<number>>(new Set())
  const [toast, setToast] = useState<{ item: ShoppingItem } | null>(null)
  const pendingTimers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map())

  const loadList = useCallback(() => {
    api.shopping.list().then(data => { setList(data); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  useEffect(() => { loadList() }, [loadList])

  function handleCheck(item: ShoppingItem) {
    if (pendingIds.has(item.id)) {
      // Already pending — undo
      handleUndo(item)
      return
    }

    // Mark as pending
    setPendingIds(prev => new Set([...prev, item.id]))
    setToast({ item })

    // Schedule actual delete
    const timer = setTimeout(async () => {
      pendingTimers.current.delete(item.id)
      setPendingIds(prev => { const s = new Set(prev); s.delete(item.id); return s })
      setToast(null)
      try {
        await api.shopping.delete(item.id)
        loadList()
      } catch {
        loadList()
      }
    }, 3000)

    pendingTimers.current.set(item.id, timer)
  }

  function handleUndo(item: ShoppingItem) {
    const timer = pendingTimers.current.get(item.id)
    if (timer) {
      clearTimeout(timer)
      pendingTimers.current.delete(item.id)
    }
    setPendingIds(prev => { const s = new Set(prev); s.delete(item.id); return s })
    setToast(null)
  }

  const allCategories = Object.entries(list.categories)
  const totalItems = allCategories.reduce((sum, [, items]) => sum + items.length, 0)

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p style={{ fontSize: 22, fontWeight: 500 }}>Shopping</p>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
              {totalItems} {totalItems === 1 ? 'item' : 'items'}
            </p>
          </div>
          <button className="add-btn" onClick={() => setShowAddModal(true)}>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M9 3v12M3 9h12" stroke="var(--text-on-dark)" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>

      <div style={{ padding: '16px 20px' }}>
        {loading ? (
          <div className="loading">Loading…</div>
        ) : totalItems === 0 ? (
          <div className="empty-state">
            <p style={{ fontSize: 32, marginBottom: 12 }}>🛒</p>
            <p>Nothing to buy — you're all set!</p>
          </div>
        ) : (
          <>
            {allCategories.map(([cat, items]) => (
              <Section
                key={cat}
                title={cat.charAt(0).toUpperCase() + cat.slice(1)}
                items={items}
                onCheck={handleCheck}
                pendingIds={pendingIds}
              />
            ))}
          </>
        )}
      </div>

      {showAddModal && (
        <AddItemModal
          onClose={() => setShowAddModal(false)}
          onSaved={loadList}
          existingCategories={Object.keys(list.categories)}
        />
      )}

      {toast && (
        <Toast
          message={`"${toast.item.name}" removed`}
          onUndo={() => handleUndo(toast.item)}
          onExpire={() => setToast(null)}
        />
      )}
    </div>
  )
}
