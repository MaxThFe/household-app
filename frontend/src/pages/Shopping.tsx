import { useState, useEffect, useCallback, useRef } from 'react'
import { api, getMarket, setMarket, MarketInfo, SectionInfo, ShoppingItem, ShoppingList } from '../api/client'
import { Modal } from '../components/Modal'
import { SectionOrderSheet } from '../components/SectionOrderSheet'
import { Toast } from '../components/Toast'

const DEFAULT_CATEGORIES = ['supermarket', 'household']

// --- Category picker, shared by the add and edit modals ---
interface PickerProps {
  existingCategories: string[]
  store: string
  onStoreChange: (store: string) => void
  customStore: string
  onCustomStoreChange: (store: string) => void
  showCustomInput: boolean
  onShowCustomInput: (show: boolean) => void
}

function CategoryPicker({
  existingCategories,
  store,
  onStoreChange,
  customStore,
  onCustomStoreChange,
  showCustomInput,
  onShowCustomInput,
}: PickerProps) {
  const customCategories = existingCategories.filter(c => !DEFAULT_CATEGORIES.includes(c))
  const allPills = [...DEFAULT_CATEGORIES, ...customCategories]

  return (
    <div className="form-group">
      <label className="form-label">Category</label>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {allPills.map(s => (
          <button
            key={s}
            className={`pill ${!showCustomInput && store === s ? 'pill-active' : 'pill-inactive'}`}
            onClick={() => { onStoreChange(s); onShowCustomInput(false) }}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
        <button
          className={`pill ${showCustomInput ? 'pill-active' : 'pill-inactive'}`}
          onClick={() => onShowCustomInput(true)}
        >
          + Custom
        </button>
      </div>
      {showCustomInput && (
        <input
          className="form-input"
          style={{ marginTop: 8 }}
          value={customStore}
          onChange={e => onCustomStoreChange(e.target.value)}
          placeholder="Category name"
          autoFocus
        />
      )}
    </div>
  )
}

// --- Add item modal ---
interface AddItemModalProps {
  existingCategories: string[]
  onClose: () => void
  onSaved: () => void
}

function AddItemModal({ onClose, onSaved, existingCategories }: AddItemModalProps) {
  const [name, setName] = useState('')
  const [quantity, setQuantity] = useState('')
  const [unit, setUnit] = useState('')
  const [store, setStore] = useState('supermarket')
  const [customStore, setCustomStore] = useState('')
  const [showCustomInput, setShowCustomInput] = useState(false)
  const [saving, setSaving] = useState(false)

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
      <CategoryPicker
        existingCategories={existingCategories}
        store={store}
        onStoreChange={setStore}
        customStore={customStore}
        onCustomStoreChange={setCustomStore}
        showCustomInput={showCustomInput}
        onShowCustomInput={setShowCustomInput}
      />
    </Modal>
  )
}

// --- Edit item modal ---
interface EditItemModalProps {
  item: ShoppingItem
  existingCategories: string[]
  onClose: () => void
  onSaved: () => void
}

function EditItemModal({ item, existingCategories, onClose, onSaved }: EditItemModalProps) {
  const [name, setName] = useState(item.name)
  const [quantity, setQuantity] = useState(item.quantity != null ? String(item.quantity) : '')
  const [unit, setUnit] = useState(item.unit)
  const [store, setStore] = useState(item.store || 'supermarket')
  const customCategories = existingCategories.filter(c => !DEFAULT_CATEGORIES.includes(c))
  const allPills = [...DEFAULT_CATEGORIES, ...customCategories]
  const [customStore, setCustomStore] = useState(!allPills.includes(item.store) && item.store ? item.store : '')
  const [showCustomInput, setShowCustomInput] = useState(!allPills.includes(item.store || 'supermarket'))
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    if (!name.trim()) return
    const finalStore = showCustomInput ? customStore.trim().toLowerCase() : store
    if (!finalStore) return
    setSaving(true)
    try {
      await api.shopping.update(item.id, {
        name: name.trim(),
        quantity: quantity ? parseFloat(quantity) : null,
        unit: unit || '',
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
      title="Edit item"
      onClose={onClose}
      footer={
        <button className="btn-primary" onClick={handleSave} disabled={saving || !name.trim() || (showCustomInput && !customStore.trim())}>
          {saving ? 'Saving…' : 'Save'}
        </button>
      }
    >
      <div className="form-group">
        <label className="form-label">Item name</label>
        <input className="form-input" value={name} onChange={e => setName(e.target.value)} autoFocus />
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
      <CategoryPicker
        existingCategories={existingCategories}
        store={store}
        onStoreChange={setStore}
        customStore={customStore}
        onCustomStoreChange={setCustomStore}
        showCustomInput={showCustomInput}
        onShowCustomInput={setShowCustomInput}
      />
    </Modal>
  )
}

// --- Shopping item row ---
interface ShoppingRowProps {
  item: ShoppingItem
  onCheck: (item: ShoppingItem) => void
  onEdit: (item: ShoppingItem) => void
  pendingIds: Set<number>
}

function ShoppingRow({ item, onCheck, onEdit, pendingIds }: ShoppingRowProps) {
  const isPending = pendingIds.has(item.id)

  return (
    <div className="shopping-item-row" style={{ opacity: isPending ? 0.4 : 1, transition: 'opacity 0.2s' }}>
      <input
        type="checkbox"
        className="shopping-checkbox"
        checked={isPending}
        onChange={() => onCheck(item)}
      />
      <div style={{ flex: 1, cursor: 'pointer' }} onClick={() => onEdit(item)}>
        <p style={{ fontSize: 14, color: 'var(--text-primary)' }}>{item.name}</p>
        {item.source_names && (
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>{item.source_names}</p>
        )}
        {item.is_manual === 1 && !item.source_names && (
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>manually added</p>
        )}
      </div>
      {item.quantity != null && (
        <p style={{ fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap', cursor: 'pointer' }} onClick={() => onEdit(item)}>
          {item.quantity}{item.unit ? ` ${item.unit}` : ''}
        </p>
      )}
    </div>
  )
}

// --- Category group, optionally split into aisle sections ---
interface SectionProps {
  title: string
  items: ShoppingItem[]
  sectionOrder: string[] | null
  sections: SectionInfo[]
  headerRight?: React.ReactNode
  onCheck: (item: ShoppingItem) => void
  onEdit: (item: ShoppingItem) => void
  pendingIds: Set<number>
}

function Section({ title, items, sectionOrder, sections, headerRight, onCheck, onEdit, pendingIds }: SectionProps) {
  if (items.length === 0) return null

  const sectionInfo = new Map(sections.map(s => [s.slug, s]))
  const grouped = sectionOrder
    ? sectionOrder
        .map(slug => ({ slug, items: items.filter(i => i.section === slug) }))
        .filter(g => g.items.length > 0)
    : []
  // Nothing gained from dividers when everything sits in one aisle
  const showSections = grouped.length > 1

  return (
    <div className="shopping-group">
      <div className="shopping-group-header">
        <span>{title}</span>
        {headerRight ?? <span>{items.length} {items.length === 1 ? 'item' : 'items'}</span>}
      </div>
      <div className="shopping-list-card">
        {showSections
          ? grouped.map(group => (
              <div key={group.slug} className="shopping-section-group">
                <div className="shopping-section-header">
                  {sectionInfo.get(group.slug)?.label ?? group.slug}
                </div>
                {group.items.map(item => (
                  <ShoppingRow key={item.id} item={item} onCheck={onCheck} onEdit={onEdit} pendingIds={pendingIds} />
                ))}
              </div>
            ))
          : items.map(item => (
              <ShoppingRow key={item.id} item={item} onCheck={onCheck} onEdit={onEdit} pendingIds={pendingIds} />
            ))}
      </div>
    </div>
  )
}

function PencilIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
      <path d="M8.2 1.8l2 2L4 10H2V8l6.2-6.2z" stroke="currentColor" strokeWidth="1.1" strokeLinejoin="round" />
    </svg>
  )
}

// --- Main shopping page ---
export default function Shopping() {
  const [list, setList] = useState<ShoppingList>({ categories: {}, sections: [], markets: [], section_orders: {} })
  const [loading, setLoading] = useState(true)
  const [showAddModal, setShowAddModal] = useState(false)
  const [showOrderSheet, setShowOrderSheet] = useState(false)
  const [editItem, setEditItem] = useState<ShoppingItem | null>(null)
  const [pendingIds, setPendingIds] = useState<Set<number>>(new Set())
  const [toast, setToast] = useState<{ item: ShoppingItem } | null>(null)
  const [market, setMarketState] = useState(getMarket())
  const pendingTimers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map())

  const loadList = useCallback(() => {
    api.shopping.list().then(data => { setList(data); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  useEffect(() => { loadList() }, [loadList])

  function selectMarket(slug: string) {
    setMarketState(slug)
    setMarket(slug)
  }

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
  const activeMarket: MarketInfo | undefined =
    list.markets.find(m => m.slug === market) ?? list.markets[0]
  const sectionOrder = activeMarket ? list.section_orders[activeMarket.slug] ?? null : null

  const marketSwitcher = activeMarket && (
    <div style={{ display: 'flex', gap: 6, marginLeft: 'auto' }}>
      {list.markets.map(m => {
        const isActive = activeMarket.slug === m.slug
        return (
          <button
            key={m.slug}
            className={`pill ${isActive ? 'pill-active' : 'pill-inactive'}`}
            style={{ gap: 6 }}
            onClick={() => selectMarket(m.slug)}
          >
            {m.label}
            {isActive && (
              <span
                role="button"
                title="Edit aisle order"
                onClick={e => { e.stopPropagation(); setShowOrderSheet(true) }}
                style={{ display: 'inline-flex', opacity: 0.65 }}
              >
                <PencilIcon />
              </span>
            )}
          </button>
        )
      })}
    </div>
  )

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
          <button className="add-btn" title="Add item" onClick={() => setShowAddModal(true)}>
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
                sectionOrder={cat === 'supermarket' ? sectionOrder : null}
                sections={list.sections}
                headerRight={cat === 'supermarket' ? marketSwitcher : undefined}
                onCheck={handleCheck}
                onEdit={setEditItem}
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

      {editItem && (
        <EditItemModal
          item={editItem}
          existingCategories={Object.keys(list.categories)}
          onClose={() => setEditItem(null)}
          onSaved={loadList}
        />
      )}

      {showOrderSheet && activeMarket && (
        <SectionOrderSheet
          market={activeMarket}
          sections={list.sections}
          order={sectionOrder ?? list.sections.map(s => s.slug)}
          onClose={() => setShowOrderSheet(false)}
          onSaved={loadList}
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
