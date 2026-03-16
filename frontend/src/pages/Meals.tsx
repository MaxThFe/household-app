import { useState, useEffect, useCallback } from 'react'
import { api, Meal, Recipe, toISOWeek, offsetWeek, getMondayFromWeek, formatDateRange, todayISO, dateISO } from '../api/client'
import { Modal } from '../components/Modal'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function AttendantBadge({ count }: { count: number }) {
  const solo = count === 1
  return (
    <div className={`attendant-badge${solo ? ' solo' : ''}`}>
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
        <circle cx="6" cy="4" r="2" stroke={solo ? '#993C1D' : '#8B7D6B'} strokeWidth="1" />
        <path d="M2.5 10.5a3.5 3.5 0 017 0" stroke={solo ? '#993C1D' : '#8B7D6B'} strokeWidth="1" />
      </svg>
      <span>{count}</span>
    </div>
  )
}

interface DayEntry {
  date: string
  day: string
  dateNum: number
  meal: Meal | undefined
  isToday: boolean
}

// --- Meal detail / create modal ---
interface MealModalProps {
  entry: DayEntry
  onClose: () => void
  onSaved: () => void
}

function MealModal({ entry, onClose, onSaved }: MealModalProps) {
  const [mode, setMode] = useState<'view' | 'edit'>('view')
  const [recipes, setRecipes] = useState<Recipe[]>([])
  const [search, setSearch] = useState('')
  const [selectedRecipe, setSelectedRecipe] = useState<Recipe | null>(null)
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set())
  const [customName, setCustomName] = useState('')
  const [useCustom, setUseCustom] = useState(false)
  const [saving, setSaving] = useState(false)

  const hasExistingMeal = !!entry.meal
  const isEditing = !hasExistingMeal || mode === 'edit'

  useEffect(() => {
    if (isEditing) {
      api.recipes.list(search).then(setRecipes).catch(() => {})
    }
  }, [search, isEditing])

  function handleSelectRecipe(r: Recipe) {
    setSelectedRecipe(r)
    setCheckedIds(new Set(r.ingredients.map(i => i.id)))
  }

  function toggleIngredient(id: number) {
    setCheckedIds(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  async function handleSave() {
    if (!selectedRecipe && !useCustom && !customName) return
    setSaving(true)
    try {
      if (entry.meal) {
        await api.meals.delete(entry.meal.id)
      }
      await api.meals.create({
        date: entry.date,
        ...(useCustom || !selectedRecipe
          ? { custom_name: customName }
          : { recipe_id: selectedRecipe.id, ingredient_ids: [...checkedIds] }),
      })
      onSaved()
      onClose()
    } catch {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!entry.meal) return
    setSaving(true)
    try {
      await api.meals.delete(entry.meal.id)
      onSaved()
      onClose()
    } catch {
      setSaving(false)
    }
  }

  const displayDate = new Date(entry.date + 'T12:00:00').toLocaleDateString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long',
  })

  // View mode — existing meal
  if (hasExistingMeal && mode === 'view') {
    const meal = entry.meal!
    return (
      <Modal
        title={displayDate}
        onClose={onClose}
        footer={
          <>
            <button className="btn-danger" onClick={handleDelete} disabled={saving}>Remove</button>
            <button className="btn-secondary" onClick={() => setMode('edit')}>Change</button>
          </>
        }
      >
        <p style={{ fontSize: 18, fontWeight: 500, marginBottom: 4 }}>
          {meal.recipe_name ?? meal.custom_name}
        </p>
        {meal.attendants === 1 && (
          <p style={{ fontSize: 13, color: 'var(--accent-orange)' }}>Solo dinner (late shift)</p>
        )}
      </Modal>
    )
  }

  // Edit / create mode
  return (
    <Modal
      title={displayDate}
      onClose={onClose}
      footer={
        <button
          className="btn-primary"
          onClick={handleSave}
          disabled={saving || (!selectedRecipe && !customName)}
        >
          {saving ? 'Saving…' : 'Confirm'}
        </button>
      }
    >
      {/* Toggle recipe vs custom */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button
          className={`pill ${!useCustom ? 'pill-active' : 'pill-inactive'}`}
          onClick={() => setUseCustom(false)}
        >
          Pick recipe
        </button>
        <button
          className={`pill ${useCustom ? 'pill-active' : 'pill-inactive'}`}
          onClick={() => setUseCustom(true)}
        >
          Custom
        </button>
      </div>

      {useCustom ? (
        <div className="form-group">
          <label className="form-label">What's for dinner?</label>
          <input
            className="form-input"
            placeholder="e.g. Eating out, Leftovers…"
            value={customName}
            onChange={e => setCustomName(e.target.value)}
            autoFocus
          />
        </div>
      ) : (
        <>
          {/* Recipe search */}
          <div className="search-input" style={{ marginTop: 0, marginBottom: 12 }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="7" cy="7" r="4.5" stroke="var(--text-secondary)" strokeWidth="1.3" />
              <path d="M10.5 10.5L14 14" stroke="var(--text-secondary)" strokeWidth="1.3" strokeLinecap="round" />
            </svg>
            <input
              placeholder="Search recipes…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              autoFocus
            />
          </div>

          {/* Recipe list */}
          {!selectedRecipe && (
            <div>
              {recipes.map(r => (
                <div
                  key={r.id}
                  className="card"
                  style={{ cursor: 'pointer' }}
                  onClick={() => handleSelectRecipe(r)}
                >
                  <p style={{ fontWeight: 500 }}>{r.name}</p>
                  <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                    {r.ingredients.map(i => i.name).join(', ')}
                  </p>
                </div>
              ))}
              {recipes.length === 0 && (
                <p style={{ color: 'var(--text-muted)', fontSize: 14, textAlign: 'center', padding: 20 }}>
                  No recipes found
                </p>
              )}
            </div>
          )}

          {/* Selected recipe + ingredient checkboxes */}
          {selectedRecipe && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <p style={{ fontWeight: 500 }}>{selectedRecipe.name}</p>
                <button
                  style={{ fontSize: 12, color: 'var(--text-secondary)', textDecoration: 'underline' }}
                  onClick={() => setSelectedRecipe(null)}
                >
                  Change
                </button>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>
                Which ingredients do you need?
              </p>
              {selectedRecipe.ingredients.map(ing => (
                <label key={ing.id} className="ingredient-row" style={{ cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    className="shopping-checkbox"
                    checked={checkedIds.has(ing.id)}
                    onChange={() => toggleIngredient(ing.id)}
                  />
                  <span style={{ flex: 1, fontSize: 14 }}>{ing.name}</span>
                  {ing.quantity && (
                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      {ing.quantity} {ing.unit}
                    </span>
                  )}
                </label>
              ))}
            </div>
          )}
        </>
      )}
    </Modal>
  )
}

// --- Main meals page ---

export default function Meals() {
  const [week, setWeek] = useState(toISOWeek(new Date()))
  const [meals, setMeals] = useState<Meal[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedEntry, setSelectedEntry] = useState<DayEntry | null>(null)

  const today = todayISO()
  const currentWeek = toISOWeek(new Date())
  const isCurrentWeek = week === currentWeek
  const monday = getMondayFromWeek(week)

  const days: DayEntry[] = DAYS.map((day, i) => {
    const d = new Date(monday)
    d.setDate(monday.getDate() + i)
    const date = dateISO(d)
    return {
      date,
      day,
      dateNum: d.getDate(),
      meal: meals.find(m => m.date === date),
      isToday: date === today,
    }
  })

  const loadMeals = useCallback(() => {
    setLoading(true)
    api.meals.list(week).then(m => { setMeals(m); setLoading(false) }).catch(() => setLoading(false))
  }, [week])

  useEffect(() => { loadMeals() }, [loadMeals])

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            {isCurrentWeek
              ? <p style={{ fontSize: 22, fontWeight: 500 }}>This week</p>
              : <p style={{ fontSize: 22, fontWeight: 500 }}>{formatDateRange(monday)}</p>
            }
            {isCurrentWeek && (
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>{formatDateRange(monday)}</p>
            )}
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {!isCurrentWeek && (
              <button className="pill pill-inactive" onClick={() => setWeek(currentWeek)}>Today</button>
            )}
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
        {loading ? (
          <div className="loading">Loading…</div>
        ) : (
          days.map(entry => {
            const { day, dateNum, meal, isToday } = entry
            const mealLabel = meal?.recipe_name ?? meal?.custom_name

            if (isToday) {
              return (
                <div key={entry.date} className="card-today" style={{ cursor: 'pointer' }} onClick={() => setSelectedEntry(entry)}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{ minWidth: 36 }}>
                        <p style={{ fontSize: 11, color: 'var(--text-on-dark-muted)' }}>{day}</p>
                        <p style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-on-dark)' }}>{dateNum}</p>
                      </div>
                      <div>
                        <p style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-on-dark)' }}>
                          {mealLabel ?? '+ Plan dinner'}
                        </p>
                        <p style={{ fontSize: 11, color: 'var(--text-on-dark-muted)', marginTop: 1 }}>today</p>
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <AttendantBadge count={meal?.attendants ?? 2} />
                      <ChevronRight light />
                    </div>
                  </div>
                </div>
              )
            }

            if (!meal) {
              return (
                <div key={entry.date} className="card-dashed" style={{ textAlign: 'left', padding: '12px 16px' }} onClick={() => setSelectedEntry(entry)}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ minWidth: 36 }}>
                      <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>{day}</p>
                      <p style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-muted)' }}>{dateNum}</p>
                    </div>
                    <p style={{ fontSize: 14, color: 'var(--text-muted)' }}>+ Plan dinner</p>
                  </div>
                </div>
              )
            }

            const isCustom = !meal.recipe_id && !!meal.custom_name

            return (
              <div key={entry.date} className="card" style={{ cursor: 'pointer' }} onClick={() => setSelectedEntry(entry)}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ minWidth: 36 }}>
                      <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>{day}</p>
                      <p style={{ fontSize: 15, fontWeight: 500 }}>{dateNum}</p>
                    </div>
                    <p style={{ fontSize: 14, fontWeight: isCustom ? 400 : 500, fontStyle: isCustom ? 'italic' : 'normal', color: isCustom ? 'var(--text-muted)' : 'var(--text-primary)' }}>
                      {mealLabel}
                    </p>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <AttendantBadge count={meal.attendants} />
                    <ChevronRight />
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>

      {selectedEntry && (
        <MealModal
          entry={selectedEntry}
          onClose={() => setSelectedEntry(null)}
          onSaved={loadMeals}
        />
      )}
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

function ChevronRight({ light }: { light?: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M5 2l4 5-4 5" stroke={light ? 'var(--text-on-dark-muted)' : 'var(--text-muted)'} strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}
