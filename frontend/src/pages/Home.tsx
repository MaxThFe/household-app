import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, CalendarEvent, Meal, ShoppingItem, toISOWeek, todayISO, dateISO, greeting } from '../api/client'

export default function Home() {
  const navigate = useNavigate()
  const today = todayISO()
  const weekStr = toISOWeek(new Date())

  const [meals, setMeals] = useState<Meal[]>([])
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [shopping, setShopping] = useState<ShoppingItem[]>([])

  useEffect(() => {
    const month = today.slice(0, 7)
    Promise.all([
      api.meals.list(weekStr),
      api.calendar.list({ month }),
      api.shopping.list(),
    ]).then(([m, e, s]) => {
      setMeals(m)
      setEvents(e)
      setShopping([...s.supermarket, ...s.household])
    }).catch(() => {})
  }, [weekStr, today])

  const todayEvents = events.filter(e => e.date === today)
  const todayShift = todayEvents.find(e => e.source === 'ics')
  const todayMeal = meals.find(m => m.date === today)

  // Next 3 days after today
  const upcoming = Array.from({ length: 3 }, (_, i) => {
    const d = new Date(today)
    d.setDate(d.getDate() + i + 1)
    const date = dateISO(d)
    const meal = meals.find(m => m.date === date)
    const shift = events.find(e => e.date === date && e.source === 'ics')
    return { date, meal, shift, day: d.toLocaleDateString('en-GB', { weekday: 'short' }) }
  })

  const shoppingPreview = shopping.slice(0, 4)
  const shoppingExtra = shopping.length > 4 ? shopping.length - 4 : 0

  const todayFormatted = new Date().toLocaleDateString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long',
  })

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{todayFormatted}</p>
        <p style={{ fontSize: 22, fontWeight: 500, marginTop: 4 }}>{greeting()}</p>
      </div>

      <div style={{ padding: '16px 20px' }}>

        {/* Shift card */}
        {todayShift && (
          <div style={{ background: '#FFF8F0', border: '0.5px solid #F0E0CC', borderRadius: 12, padding: '14px 16px', marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)' }}>Margaux's shift</span>
            </div>
            <p style={{ fontSize: 15, fontWeight: 500 }}>{todayShift.title}</p>
            {(todayShift.start_time || todayShift.end_time) && (
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
                {todayShift.start_time} – {todayShift.end_time}
              </p>
            )}
          </div>
        )}

        {/* Today's dinner */}
        <div style={{ marginBottom: 20 }}>
          <p className="section-label">Dinner tonight</p>
          {todayMeal ? (
            <div className="card" style={{ cursor: 'pointer' }} onClick={() => navigate('/meals')}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <p style={{ fontSize: 15, fontWeight: 500 }}>
                  {todayMeal.recipe_name ?? todayMeal.custom_name}
                </p>
                <ChevronRight />
              </div>
            </div>
          ) : (
            <div className="card-dashed" onClick={() => navigate('/meals')}>
              + Plan dinner
            </div>
          )}
        </div>

        {/* Shopping preview */}
        {shopping.length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <p className="section-label" style={{ margin: 0 }}>Still to buy</p>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{shopping.length} items</span>
            </div>
            <div className="card" style={{ cursor: 'pointer' }} onClick={() => navigate('/shopping')}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {shoppingPreview.map(item => (
                  <span
                    key={item.id}
                    style={{ fontSize: 12, background: 'var(--bg-page)', color: 'var(--text-primary)', padding: '4px 10px', borderRadius: 20, border: '0.5px solid var(--border)' }}
                  >
                    {item.name}
                  </span>
                ))}
                {shoppingExtra > 0 && (
                  <span style={{ fontSize: 12, color: 'var(--text-muted)', padding: '4px 10px' }}>+{shoppingExtra} more</span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Coming up */}
        <div>
          <p className="section-label">Coming up</p>
          <div style={{ display: 'flex', gap: 8 }}>
            {upcoming.map(({ date, meal, shift, day }) => (
              <div
                key={date}
                className="card"
                style={{ flex: 1, textAlign: 'center', cursor: 'pointer', marginBottom: 0 }}
                onClick={() => navigate('/meals')}
              >
                <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>{day}</p>
                <p style={{ fontSize: 14, fontWeight: meal ? 500 : 400, color: meal ? 'var(--text-primary)' : 'var(--text-muted)', margin: '2px 0' }}>
                  {meal ? (meal.recipe_name ?? meal.custom_name) : 'No plan'}
                </p>
                {shift && <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{shift.title || 'Shift'}</p>}
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  )
}

function ChevronRight() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M6 12l4-4-4-4" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}
