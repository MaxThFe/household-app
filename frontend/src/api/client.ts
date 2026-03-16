const BASE = '/api/v1'

export function getPin(): string {
  return localStorage.getItem('ht_pin') ?? ''
}

export function setPin(pin: string): void {
  localStorage.setItem('ht_pin', pin)
}

export function clearPin(): void {
  localStorage.removeItem('ht_pin')
}

function authHeaders(): Record<string, string> {
  return { 'X-User-Pin': getPin(), 'Content-Type': 'application/json' }
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  if (res.status === 401) {
    clearPin()
    window.dispatchEvent(new Event('ht:unauthorized'))
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${res.status}: ${text}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// --- Types ---

export interface Ingredient {
  id: number
  recipe_id: number
  name: string
  quantity: number | null
  unit: string
}

export interface Recipe {
  id: number
  name: string
  tags: string
  notes: string
  created_at: string
  ingredients: Ingredient[]
}

export interface Meal {
  id: number
  date: string
  recipe_id: number | null
  recipe_name: string | null
  custom_name: string | null
  notes: string
  attendants: number
}

export interface ShoppingItem {
  id: number
  name: string
  quantity: number | null
  unit: string
  store: string
  source_recipe_id: number | null
  source_meal_id: number | null
  is_manual: number
  added_at: string
  source_names: string | null
}

export interface ShoppingList {
  supermarket: ShoppingItem[]
  household: ShoppingItem[]
}

export interface CalendarEvent {
  id: number
  date: string
  title: string
  start_time: string | null
  end_time: string | null
  all_day: number
  source: string
  source_uid: string | null
  color: string
  notes: string
}

export interface AppConfig {
  user1_name: string
  user2_name: string
}

// --- API methods ---

export const api = {
  config: {
    get: () => request<AppConfig>(`${BASE}/config`),
  },

  recipes: {
    list: (search?: string, tag?: string) => {
      const params = new URLSearchParams()
      if (search) params.set('search', search)
      if (tag) params.set('tag', tag)
      const qs = params.toString()
      return request<Recipe[]>(`${BASE}/recipes${qs ? `?${qs}` : ''}`)
    },
    get: (id: number) => request<Recipe>(`${BASE}/recipes/${id}`),
    create: (data: { name: string; tags: string; notes: string; ingredients: Omit<Ingredient, 'id' | 'recipe_id'>[] }) =>
      request<Recipe>(`${BASE}/recipes`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(data),
      }),
    update: (id: number, data: { name?: string; tags?: string; notes?: string; ingredients?: Omit<Ingredient, 'id' | 'recipe_id'>[] }) =>
      request<Recipe>(`${BASE}/recipes/${id}`, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<void>(`${BASE}/recipes/${id}`, { method: 'DELETE', headers: authHeaders() }),
  },

  meals: {
    list: (week?: string) => {
      const qs = week ? `?week=${encodeURIComponent(week)}` : ''
      return request<Meal[]>(`${BASE}/meals${qs}`)
    },
    create: (data: {
      date: string
      recipe_id?: number
      custom_name?: string
      notes?: string
      ingredient_ids?: number[]
    }) =>
      request<Meal>(`${BASE}/meals`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(data),
      }),
    update: (id: number, data: { notes?: string; attendants?: number }) =>
      request<Meal>(`${BASE}/meals/${id}`, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<void>(`${BASE}/meals/${id}`, { method: 'DELETE', headers: authHeaders() }),
  },

  shopping: {
    list: () => request<ShoppingList>(`${BASE}/shopping`),
    add: (data: { name: string; quantity?: number; unit?: string; store?: string }) =>
      request<ShoppingItem>(`${BASE}/shopping`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<void>(`${BASE}/shopping/${id}`, { method: 'DELETE', headers: authHeaders() }),
    deleteChecked: (ids: number[]) => {
      const qs = ids.map(id => `ids=${id}`).join('&')
      return request<void>(`${BASE}/shopping/checked?${qs}`, {
        method: 'DELETE',
        headers: authHeaders(),
      })
    },
  },

  calendar: {
    list: (opts?: { start?: string; end?: string; month?: string }) => {
      const params = new URLSearchParams()
      if (opts?.start) params.set('start', opts.start)
      if (opts?.end) params.set('end', opts.end)
      if (opts?.month) params.set('month', opts.month)
      const qs = params.toString()
      return request<CalendarEvent[]>(`${BASE}/calendar${qs ? `?${qs}` : ''}`)
    },
    create: (data: {
      date: string
      title: string
      start_time?: string
      end_time?: string
      all_day?: number
      color?: string
      notes?: string
    }) =>
      request<CalendarEvent>(`${BASE}/calendar`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(data),
      }),
    update: (id: number, data: Partial<{ title: string; date: string; start_time: string; end_time: string; all_day: number; color: string; notes: string }>) =>
      request<CalendarEvent>(`${BASE}/calendar/${id}`, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<void>(`${BASE}/calendar/${id}`, { method: 'DELETE', headers: authHeaders() }),
    sync: () =>
      request<void>(`${BASE}/calendar/sync`, { method: 'POST', headers: authHeaders() }),
  },
}

// --- Week helpers ---

export function toISOWeek(date: Date): string {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()))
  d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7))
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1))
  const week = Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7)
  return `${d.getUTCFullYear()}-W${String(week).padStart(2, '0')}`
}

export function getMondayFromWeek(isoWeek: string): Date {
  const [yearStr, wStr] = isoWeek.split('-W')
  const year = parseInt(yearStr)
  const week = parseInt(wStr)
  const simple = new Date(year, 0, 1 + (week - 1) * 7)
  const dow = simple.getDay()
  const monday = new Date(simple)
  monday.setDate(simple.getDate() - (dow <= 4 ? dow - 1 : dow - 8))
  return monday
}

export function offsetWeek(isoWeek: string, delta: number): string {
  const monday = getMondayFromWeek(isoWeek)
  monday.setDate(monday.getDate() + delta * 7)
  return toISOWeek(monday)
}

export function formatDateRange(monday: Date): string {
  const sunday = new Date(monday)
  sunday.setDate(monday.getDate() + 6)
  const fmt = (d: Date) =>
    d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long' })
  if (monday.getMonth() === sunday.getMonth()) {
    return `${monday.getDate()} – ${fmt(sunday)}`
  }
  return `${fmt(monday)} – ${fmt(sunday)}`
}

export function todayISO(): string {
  return new Date().toISOString().slice(0, 10)
}

export function greeting(): string {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}
