const BASE = '/api/v1'

export function getUser(): string {
  return localStorage.getItem('ht_user') ?? ''
}

export function setUser(name: string): void {
  localStorage.setItem('ht_user', name)
}

export function clearUser(): void {
  localStorage.removeItem('ht_user')
}

// Selected supermarket for the shopping list aisle order (view-only preference)
export function getMarket(): string {
  return localStorage.getItem('ht_market') ?? 'lidl'
}

export function setMarket(market: string): void {
  localStorage.setItem('ht_market', market)
}

function authHeaders(): Record<string, string> {
  return { 'X-User': getUser(), 'Content-Type': 'application/json' }
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  if (res.status === 401) {
    clearUser()
    window.dispatchEvent(new Event('ht:unauthorized'))
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${res.status}: ${text}`)
  }
  if (res.status === 204) return undefined as T
  const contentType = res.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) {
    // Cloudflare Access session expired — reload to trigger login
    window.location.reload()
    throw new Error('Session expired')
  }
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
  section: string
}

export interface SectionInfo {
  slug: string
  label: string
}

export interface MarketInfo {
  slug: string
  label: string
}

export interface ShoppingList {
  categories: Record<string, ShoppingItem[]>
  sections: SectionInfo[]
  markets: MarketInfo[]
  section_orders: Record<string, string[]>
}

export type RecurUnit = 'day' | 'week' | 'month'

export interface Task {
  id: number
  title: string
  // null for a one-off task; otherwise it repeats every recur_every units.
  recur_unit: RecurUnit | null
  recur_every: number
  // Internal bookkeeping, never shown as a date: null means "wanted now".
  next_due: string | null
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

export interface VacuumScheduleEntry {
  date: string
  shift_type: string | null
  clean_time: string | null
  is_default: boolean
}

export interface SensorReading {
  room: string
  mac: string
  temperature: number | null
  humidity: number | null
  battery: number | null
  voltage: number | null
  rssi: number | null
  last_seen: string | null
  stale: boolean
}

export interface SensorSeries {
  room: string
  metric: string
  unit: string
}

export interface SensorSeriesInfo extends SensorSeries {
  // Extent of stored history; null until the first sample lands.
  first_ts: number | null
  last_ts: number | null
}

export interface SensorHistory extends SensorSeries {
  // True when the range held more points than asked for and they were averaged.
  bucketed: boolean
  points: [number, number][]
  // Moments a window looks to have been opened, from the raw rows. Temperature
  // only; every other metric carries an empty list.
  openings: number[]
}

export interface PicnicProduct {
  product_id: string
  name: string
  unit_quantity: string
  price: number | null  // cents
  image_url: string | null
}

export interface PicnicStatus {
  // connected: this user can order into their own cart; any_connected: items can be matched.
  connected: boolean
  any_connected: boolean
  llm_configured: boolean
  running: boolean
  total: number
  done: number
  error: string | null
  open_questions: number
  pending_items: number
}

export interface PicnicQuestion {
  id: number
  item_key: string
  recipe_id: number
  recipe_names: string
  question: string
  candidates: PicnicProduct[]
}

export interface PicnicAnswer {
  product_id?: string
  text?: string
  skip?: boolean
  scope?: 'global' | 'recipe'
}

export interface PicnicMapping {
  id: number
  item_key: string
  recipe_id: number
  recipe_name: string | null
  status: 'mapped' | 'skip'
  product: PicnicProduct | null
  source: string
  updated_at: string
}

export interface PicnicOrderLine extends PicnicProduct {
  count: number
  items: string[]
}

export interface PicnicOrderPreview {
  lines: PicnicOrderLine[]
  unmapped: string[]
  skipped: string[]
}

export interface PicnicOrderResult {
  product_id: string
  ok: boolean
  error: string | null
}

// --- API methods ---

export const api = {
  config: {
    get: () => request<AppConfig>(`${BASE}/config`),
  },

  sensors: {
    list: () => request<SensorReading[]>(`${BASE}/sensors`),
    series: () => request<SensorSeriesInfo[]>(`${BASE}/sensors/series`),
    history: (start: Date, end: Date, series: string[]) => {
      const params = new URLSearchParams({
        start: start.toISOString(),
        end: end.toISOString(),
      })
      series.forEach(s => params.append('series', s))
      return request<SensorHistory[]>(`${BASE}/sensors/history?${params}`)
    },
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
    update: (id: number, data: { name?: string; quantity?: number | null; unit?: string; store?: string }) =>
      request<ShoppingItem>(`${BASE}/shopping/${id}`, {
        method: 'PATCH',
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
    setSectionOrder: (market: string, order: string[]) =>
      request<void>(`${BASE}/shopping/sections/order`, {
        method: 'PUT',
        headers: authHeaders(),
        body: JSON.stringify({ market, order }),
      }),
  },

  picnic: {
    status: () => request<PicnicStatus>(`${BASE}/picnic/status`, { headers: authHeaders() }),
    resolve: () =>
      request<PicnicStatus>(`${BASE}/picnic/resolve`, { method: 'POST', headers: authHeaders() }),
    questions: () => request<PicnicQuestion[]>(`${BASE}/picnic/questions`),
    answer: (id: number, data: PicnicAnswer) =>
      request<{ result: 'mapped' | 'skipped' | 'asked' }>(`${BASE}/picnic/questions/${id}/answer`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(data),
      }),
    mappings: () => request<PicnicMapping[]>(`${BASE}/picnic/mappings`),
    reask: (id: number) =>
      request<{ result: 'mapped' | 'skipped' | 'asked' }>(`${BASE}/picnic/mappings/${id}/reask`, {
        method: 'POST',
        headers: authHeaders(),
      }),
    forget: (id: number) =>
      request<void>(`${BASE}/picnic/mappings/${id}`, { method: 'DELETE', headers: authHeaders() }),
    preview: () => request<PicnicOrderPreview>(`${BASE}/picnic/order-preview`),
    order: (lines: { product_id: string; count: number }[]) =>
      request<PicnicOrderResult[]>(`${BASE}/picnic/order`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ lines }),
      }),
  },

  tasks: {
    list: () => request<Task[]>(`${BASE}/tasks`),
    add: (data: { title: string; recur_unit?: RecurUnit | null; recur_every?: number }) =>
      request<Task>(`${BASE}/tasks`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(data),
      }),
    update: (id: number, data: { title?: string; recur_unit?: RecurUnit | null; recur_every?: number }) =>
      request<Task>(`${BASE}/tasks/${id}`, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify(data),
      }),
    // The local date goes along, so a chore ticked off at midnight recurs from
    // the day the household is having, not the server's.
    complete: (id: number) =>
      request<void>(`${BASE}/tasks/${id}/complete`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ completed_on: todayISO() }),
      }),
    delete: (id: number) =>
      request<void>(`${BASE}/tasks/${id}`, { method: 'DELETE', headers: authHeaders() }),
  },

  vacuum: {
    schedule: (start: string, end: string) =>
      request<VacuumScheduleEntry[]>(`${BASE}/vacuum/schedule?start=${start}&end=${end}`),
    setOverride: (date: string, clean_time: string) =>
      request<void>(`${BASE}/vacuum/overrides/${date}`, {
        method: 'PUT',
        headers: authHeaders(),
        body: JSON.stringify({ clean_time }),
      }),
    deleteCleaning: (date: string) =>
      request<void>(`${BASE}/vacuum/overrides/${date}`, {
        method: 'DELETE',
        headers: authHeaders(),
      }),
    restore: (date: string) =>
      request<void>(`${BASE}/vacuum/overrides/${date}/restore`, {
        method: 'POST',
        headers: authHeaders(),
      }),
    washAndGoto: () =>
      request<void>(`${BASE}/vacuum/wash-and-goto`, {
        method: 'POST',
        headers: authHeaders(),
      }),
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

export function dateISO(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function todayISO(): string {
  return dateISO(new Date())
}

// --- Task helpers ---

/** On the board? One-offs always are; a recurring chore once its period is up. */
export function isTaskDue(task: Task, today: string = todayISO()): boolean {
  return !task.next_due || task.next_due <= today
}

/** "Weekly", "Every 3 months", or "" for a one-off. */
export function recurrenceLabel(task: Pick<Task, 'recur_unit' | 'recur_every'>): string {
  if (!task.recur_unit) return ''
  if (task.recur_every === 1) {
    return { day: 'Daily', week: 'Weekly', month: 'Monthly' }[task.recur_unit]
  }
  return `Every ${task.recur_every} ${task.recur_unit}s`
}

export function greeting(): string {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}
