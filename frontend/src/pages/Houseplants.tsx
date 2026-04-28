import { useState, useEffect, useCallback, useRef } from 'react'
import { api, Houseplant } from '../api/client'
import { Modal } from '../components/Modal'
import { Toast } from '../components/Toast'

const MAX_IMAGE_DIM = 400
const JPEG_QUALITY = 0.8

async function fileToResizedDataUrl(file: File): Promise<string> {
  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, MAX_IMAGE_DIM / Math.max(bitmap.width, bitmap.height))
  const w = Math.round(bitmap.width * scale)
  const h = Math.round(bitmap.height * scale)
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas not supported')
  ctx.drawImage(bitmap, 0, 0, w, h)
  bitmap.close()
  return canvas.toDataURL('image/jpeg', JPEG_QUALITY)
}

function urgencyStyle(daysUntilDue: number): { color: string; label: string } {
  if (daysUntilDue < 0) {
    const d = -daysUntilDue
    return { color: '#C0392B', label: `${d} day${d === 1 ? '' : 's'} overdue` }
  }
  if (daysUntilDue === 0) return { color: '#C0392B', label: 'Needs water today' }
  if (daysUntilDue <= 2) return { color: '#B7791F', label: `Water in ${daysUntilDue} day${daysUntilDue === 1 ? '' : 's'}` }
  return { color: 'var(--text-muted)', label: `Water in ${daysUntilDue} days` }
}

// --- Photo picker ---
function PhotoPicker({ value, onChange }: { value: string | null; onChange: (v: string | null) => void }) {
  const cameraRef = useRef<HTMLInputElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setBusy(true)
    try {
      const dataUrl = await fileToResizedDataUrl(file)
      onChange(dataUrl)
    } catch {
      // ignore — input keeps prior value
    } finally {
      setBusy(false)
      e.target.value = ''
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: 12,
          background: 'var(--bg-page)',
          border: '0.5px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
          flexShrink: 0,
        }}
      >
        {value ? (
          <img src={value} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <span style={{ fontSize: 28 }}>🌱</span>
        )}
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button
          type="button"
          className="pill pill-inactive"
          onClick={() => cameraRef.current?.click()}
          disabled={busy}
        >
          {busy ? 'Processing…' : '📷 Camera'}
        </button>
        <button
          type="button"
          className="pill pill-inactive"
          onClick={() => fileRef.current?.click()}
          disabled={busy}
        >
          📁 From device
        </button>
        {value && (
          <button type="button" className="pill pill-inactive" onClick={() => onChange(null)}>
            Remove
          </button>
        )}
      </div>
      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleFile}
        style={{ display: 'none' }}
      />
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        onChange={handleFile}
        style={{ display: 'none' }}
      />
    </div>
  )
}

// --- Add modal ---
function AddPlantModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState('')
  const [frequency, setFrequency] = useState('7')
  const [imageData, setImageData] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const freqNum = parseInt(frequency, 10)
  const valid = name.trim().length > 0 && Number.isFinite(freqNum) && freqNum > 0

  async function handleSave() {
    if (!valid) return
    setSaving(true)
    try {
      await api.houseplants.add({
        name: name.trim(),
        watering_frequency_days: freqNum,
        image_data: imageData,
      })
      onSaved()
      onClose()
    } catch {
      setSaving(false)
    }
  }

  return (
    <Modal
      title="Add plant"
      onClose={onClose}
      footer={
        <button className="btn-primary" onClick={handleSave} disabled={saving || !valid}>
          {saving ? 'Saving…' : 'Add'}
        </button>
      }
    >
      <div className="form-group">
        <label className="form-label">Photo</label>
        <PhotoPicker value={imageData} onChange={setImageData} />
      </div>
      <div className="form-group">
        <label className="form-label">Plant name</label>
        <input
          className="form-input"
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="e.g. Monstera"
          autoFocus
        />
      </div>
      <div className="form-group">
        <label className="form-label">Water every (days)</label>
        <input
          className="form-input"
          type="number"
          min="1"
          value={frequency}
          onChange={e => setFrequency(e.target.value)}
        />
      </div>
    </Modal>
  )
}

// --- Edit modal ---
function EditPlantModal({
  plant,
  onClose,
  onSaved,
  onDelete,
}: {
  plant: Houseplant
  onClose: () => void
  onSaved: () => void
  onDelete: (plant: Houseplant) => void
}) {
  const [name, setName] = useState(plant.name)
  const [frequency, setFrequency] = useState(String(plant.watering_frequency_days))
  const [imageData, setImageData] = useState<string | null>(plant.image_data)
  const [saving, setSaving] = useState(false)

  const freqNum = parseInt(frequency, 10)
  const valid = name.trim().length > 0 && Number.isFinite(freqNum) && freqNum > 0

  async function handleSave() {
    if (!valid) return
    setSaving(true)
    try {
      await api.houseplants.update(plant.id, {
        name: name.trim(),
        watering_frequency_days: freqNum,
        image_data: imageData,
      })
      onSaved()
      onClose()
    } catch {
      setSaving(false)
    }
  }

  return (
    <Modal
      title="Edit plant"
      onClose={onClose}
      footer={
        <div style={{ display: 'flex', gap: 8, width: '100%' }}>
          <button
            className="pill pill-inactive"
            style={{ color: '#C0392B' }}
            onClick={() => { onDelete(plant); onClose() }}
          >
            Delete
          </button>
          <div style={{ flex: 1 }} />
          <button className="btn-primary" onClick={handleSave} disabled={saving || !valid}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      }
    >
      <div className="form-group">
        <label className="form-label">Photo</label>
        <PhotoPicker value={imageData} onChange={setImageData} />
      </div>
      <div className="form-group">
        <label className="form-label">Plant name</label>
        <input
          className="form-input"
          value={name}
          onChange={e => setName(e.target.value)}
          autoFocus
        />
      </div>
      <div className="form-group">
        <label className="form-label">Water every (days)</label>
        <input
          className="form-input"
          type="number"
          min="1"
          value={frequency}
          onChange={e => setFrequency(e.target.value)}
        />
      </div>
    </Modal>
  )
}

// --- Plant row ---
function PlantRow({
  plant,
  onWater,
  onEdit,
  watering,
}: {
  plant: Houseplant
  onWater: (plant: Houseplant) => void
  onEdit: (plant: Houseplant) => void
  watering: boolean
}) {
  const { color, label } = urgencyStyle(plant.days_until_due)

  return (
    <div
      className="card"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        cursor: 'pointer',
        marginBottom: 10,
      }}
      onClick={() => onEdit(plant)}
    >
      <div
        style={{
          width: 48,
          height: 48,
          borderRadius: '50%',
          background: 'var(--bg-page)',
          border: '0.5px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
          flexShrink: 0,
        }}
      >
        {plant.image_data ? (
          <img src={plant.image_data} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <span style={{ fontSize: 22 }}>🌱</span>
        )}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)' }}>{plant.name}</p>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
          every {plant.watering_frequency_days} day{plant.watering_frequency_days === 1 ? '' : 's'}
        </p>
        <p style={{ fontSize: 12, color, marginTop: 2 }}>{label}</p>
      </div>
      <button
        className="pill pill-inactive"
        onClick={e => { e.stopPropagation(); onWater(plant) }}
        disabled={watering}
        style={{ flexShrink: 0 }}
      >
        💧 Water
      </button>
    </div>
  )
}

// --- Main page ---
export default function Houseplants() {
  const [plants, setPlants] = useState<Houseplant[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [editPlant, setEditPlant] = useState<Houseplant | null>(null)
  const [wateringId, setWateringId] = useState<number | null>(null)
  const [pendingDelete, setPendingDelete] = useState<Houseplant | null>(null)
  const deleteTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const load = useCallback(() => {
    api.houseplants.list()
      .then(p => { setPlants(p); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  async function handleWater(plant: Houseplant) {
    setWateringId(plant.id)
    try {
      await api.houseplants.water(plant.id)
      load()
    } finally {
      setWateringId(null)
    }
  }

  function scheduleDelete(plant: Houseplant) {
    // Optimistically hide the plant
    setPlants(prev => prev.filter(p => p.id !== plant.id))
    setPendingDelete(plant)
    if (deleteTimer.current) clearTimeout(deleteTimer.current)
    deleteTimer.current = setTimeout(async () => {
      deleteTimer.current = null
      setPendingDelete(null)
      try {
        await api.houseplants.delete(plant.id)
      } catch {
        // re-fetch on error to restore state
      } finally {
        load()
      }
    }, 3000)
  }

  function undoDelete() {
    if (deleteTimer.current) {
      clearTimeout(deleteTimer.current)
      deleteTimer.current = null
    }
    setPendingDelete(null)
    load()
  }

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p style={{ fontSize: 22, fontWeight: 500 }}>Plants</p>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
              {plants.length} {plants.length === 1 ? 'plant' : 'plants'}
            </p>
          </div>
          <button className="add-btn" onClick={() => setShowAdd(true)}>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M9 3v12M3 9h12" stroke="var(--text-on-dark)" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>

      <div style={{ padding: '16px 20px' }}>
        {loading ? (
          <div className="loading">Loading…</div>
        ) : plants.length === 0 ? (
          <div className="empty-state">
            <p style={{ fontSize: 32, marginBottom: 12 }}>🌱</p>
            <p>No plants yet — add your first one!</p>
          </div>
        ) : (
          plants.map(plant => (
            <PlantRow
              key={plant.id}
              plant={plant}
              onWater={handleWater}
              onEdit={setEditPlant}
              watering={wateringId === plant.id}
            />
          ))
        )}
      </div>

      {showAdd && (
        <AddPlantModal onClose={() => setShowAdd(false)} onSaved={load} />
      )}

      {editPlant && (
        <EditPlantModal
          plant={editPlant}
          onClose={() => setEditPlant(null)}
          onSaved={load}
          onDelete={scheduleDelete}
        />
      )}

      {pendingDelete && (
        <Toast
          message={`"${pendingDelete.name}" removed`}
          onUndo={undoDelete}
          onExpire={() => setPendingDelete(null)}
        />
      )}
    </div>
  )
}
