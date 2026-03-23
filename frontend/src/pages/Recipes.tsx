import { useState, useEffect, useCallback, useRef } from 'react'
import { api, Recipe, Ingredient } from '../api/client'
import { Modal } from '../components/Modal'

const ALL_TAGS = ['Quick', 'Veggie', 'Vegan', 'Pasta', 'Rice', 'Soup', 'Salad', 'Meat', 'Fish', 'Breakfast']

// --- Recipe form ---
interface IngredientDraft {
  name: string
  quantity: string
  unit: string
}

interface RecipeFormProps {
  initial?: Recipe
  onClose: () => void
  onSaved: () => void
}

function RecipeForm({ initial, onClose, onSaved }: RecipeFormProps) {
  const [name, setName] = useState(initial?.name ?? '')
  const [selectedTags, setSelectedTags] = useState<Set<string>>(
    () => new Set(initial?.tags ? initial.tags.split(',').map(t => t.trim()).filter(Boolean) : [])
  )
  const [notes, setNotes] = useState(initial?.notes ?? '')
  const [ingredients, setIngredients] = useState<IngredientDraft[]>(
    initial?.ingredients.map(i => ({ name: i.name, quantity: i.quantity?.toString() ?? '1', unit: i.unit })) ?? [{ name: '', quantity: '1', unit: '' }]
  )
  const [saving, setSaving] = useState(false)
  const [focusLastIngredient, setFocusLastIngredient] = useState(false)
  const ingredientNameRefs = useRef<(HTMLInputElement | null)[]>([])

  useEffect(() => {
    if (focusLastIngredient) {
      ingredientNameRefs.current[ingredients.length - 1]?.focus()
      setFocusLastIngredient(false)
    }
  }, [focusLastIngredient, ingredients.length])

  function toggleTag(tag: string) {
    setSelectedTags(prev => {
      const next = new Set(prev)
      next.has(tag) ? next.delete(tag) : next.add(tag)
      return next
    })
  }

  function addIngredient() {
    setIngredients(prev => [...prev, { name: '', quantity: '1', unit: '' }])
    setFocusLastIngredient(true)
  }

  function updateIngredient(i: number, field: keyof IngredientDraft, val: string) {
    setIngredients(prev => prev.map((ing, idx) => idx === i ? { ...ing, [field]: val } : ing))
  }

  function removeIngredient(i: number) {
    setIngredients(prev => prev.filter((_, idx) => idx !== i))
  }

  async function handleSave() {
    if (!name.trim()) return
    setSaving(true)
    const tags = [...selectedTags].join(',')
    const ings = ingredients
      .filter(i => i.name.trim())
      .map(i => ({ name: i.name.trim(), quantity: i.quantity ? parseFloat(i.quantity) : null, unit: i.unit }))

    try {
      if (initial) {
        await api.recipes.update(initial.id, { name: name.trim(), tags, notes, ingredients: ings as Omit<Ingredient, 'id' | 'recipe_id'>[] })
      } else {
        await api.recipes.create({ name: name.trim(), tags, notes, ingredients: ings as Omit<Ingredient, 'id' | 'recipe_id'>[] })
      }
      onSaved()
      onClose()
    } catch {
      setSaving(false)
    }
  }

  return (
    <Modal
      title={initial ? 'Edit recipe' : 'New recipe'}
      onClose={onClose}
      footer={
        <button className="btn-primary" onClick={handleSave} disabled={saving || !name.trim()}>
          {saving ? 'Saving…' : 'Save'}
        </button>
      }
    >
      <div className="form-group">
        <label className="form-label">Name</label>
        <input className="form-input" value={name} onChange={e => setName(e.target.value)} placeholder="Recipe name" autoFocus />
      </div>
      <div className="form-group">
        <label className="form-label">Tags</label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {ALL_TAGS.map(tag => (
            <button
              key={tag}
              type="button"
              className={`pill ${selectedTags.has(tag) ? 'pill-active' : 'pill-inactive'}`}
              onClick={() => toggleTag(tag)}
            >
              {tag}
            </button>
          ))}
        </div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <label className="form-label" style={{ margin: 0 }}>Ingredients</label>
          <button style={{ fontSize: 12, color: 'var(--text-secondary)', textDecoration: 'underline' }} onClick={addIngredient}>
            + Add
          </button>
        </div>
        {ingredients.map((ing, i) => (
          <div key={i} className="ingredient-add-row">
            <input
              className="form-input"
              style={{ flex: 2 }}
              placeholder="Name"
              value={ing.name}
              ref={el => { ingredientNameRefs.current[i] = el }}
              onChange={e => updateIngredient(i, 'name', e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addIngredient() } }}
            />
            <input
              className="form-input"
              style={{ flex: 1 }}
              placeholder="Qty"
              type="number"
              value={ing.quantity}
              onChange={e => updateIngredient(i, 'quantity', e.target.value)}
            />
            <input
              className="form-input"
              style={{ flex: 1 }}
              placeholder="Unit"
              value={ing.unit}
              onChange={e => updateIngredient(i, 'unit', e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addIngredient() } }}
            />
            <button onClick={() => removeIngredient(i)} style={{ color: 'var(--accent-red)', fontSize: 18, padding: '0 4px' }}>×</button>
          </div>
        ))}
      </div>

      <div className="form-group">
        <label className="form-label">Notes</label>
        <textarea
          className="form-input"
          rows={3}
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder="Optional notes…"
          style={{ resize: 'vertical' }}
        />
      </div>
    </Modal>
  )
}

// --- Recipe detail ---
interface RecipeDetailProps {
  recipe: Recipe
  onClose: () => void
  onDeleted: () => void
  onEdit: () => void
}

function RecipeDetail({ recipe, onClose, onDeleted, onEdit }: RecipeDetailProps) {
  const [deleting, setDeleting] = useState(false)

  async function handleDelete() {
    if (!confirm(`Delete "${recipe.name}"?`)) return
    setDeleting(true)
    try {
      await api.recipes.delete(recipe.id)
      onDeleted()
      onClose()
    } catch {
      setDeleting(false)
    }
  }

  const tagList = recipe.tags ? recipe.tags.split(',').map(t => t.trim()).filter(Boolean) : []

  return (
    <Modal
      title={recipe.name}
      onClose={onClose}
      footer={
        <>
          <button className="btn-danger" onClick={handleDelete} disabled={deleting}>Delete</button>
          <button className="btn-primary" onClick={onEdit}>Edit</button>
        </>
      }
    >
      {tagList.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
          {tagList.map(t => <span key={t} className="tag-pill">{t}</span>)}
        </div>
      )}

      {recipe.ingredients.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.4 }}>
            Ingredients
          </p>
          {recipe.ingredients.map(ing => (
            <div key={ing.id} className="ingredient-row">
              <span style={{ flex: 1, fontSize: 14 }}>{ing.name}</span>
              {ing.quantity && (
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{ing.quantity} {ing.unit}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {recipe.notes && (
        <div>
          <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.4 }}>Notes</p>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{recipe.notes}</p>
        </div>
      )}
    </Modal>
  )
}

// --- Main recipes page ---

export default function Recipes() {
  const [recipes, setRecipes] = useState<Recipe[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Recipe | null>(null)
  const [editing, setEditing] = useState<Recipe | null | 'new'>(null)

  const loadRecipes = useCallback(() => {
    setLoading(true)
    api.recipes.list(search)
      .then(data => { setRecipes(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [search])

  useEffect(() => { loadRecipes() }, [loadRecipes])

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <p style={{ fontSize: 22, fontWeight: 500 }}>Recipes</p>
          <button className="add-btn" onClick={() => setEditing('new')}>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M9 3v12M3 9h12" stroke="var(--text-on-dark)" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        <div className="search-input">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="7" cy="7" r="4.5" stroke="var(--text-secondary)" strokeWidth="1.3" />
            <path d="M10.5 10.5L14 14" stroke="var(--text-secondary)" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
          <input
            placeholder="Search recipes…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

      </div>

      <div style={{ padding: '16px 20px' }}>
        {!loading && (
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
            {recipes.length} {recipes.length === 1 ? 'recipe' : 'recipes'}
          </p>
        )}

        {loading ? (
          <div className="loading">Loading…</div>
        ) : recipes.length === 0 ? (
          <div className="empty-state">
            {search ? 'No matching recipes' : 'No recipes yet. Add one!'}
          </div>
        ) : (
          recipes.map(recipe => {
            const tagList = recipe.tags ? recipe.tags.split(',').map(t => t.trim()).filter(Boolean) : []
            return (
              <div
                key={recipe.id}
                className="card"
                style={{ cursor: 'pointer' }}
                onClick={() => setSelected(recipe)}
              >
                <p style={{ fontSize: 15, fontWeight: 500 }}>{recipe.name}</p>
                {recipe.ingredients.length > 0 && (
                  <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.4 }}>
                    {recipe.ingredients.map(i => i.name).join(', ')}
                  </p>
                )}
                {tagList.length > 0 && (
                  <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                    {tagList.map(t => <span key={t} className="tag-pill">{t}</span>)}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      {selected && editing === null && (
        <RecipeDetail
          recipe={selected}
          onClose={() => setSelected(null)}
          onDeleted={() => { loadRecipes(); setSelected(null) }}
          onEdit={() => setEditing(selected)}
        />
      )}

      {editing !== null && (
        <RecipeForm
          initial={typeof editing === 'object' ? editing : undefined}
          onClose={() => setEditing(null)}
          onSaved={() => { loadRecipes(); setEditing(null); setSelected(null) }}
        />
      )}
    </div>
  )
}
