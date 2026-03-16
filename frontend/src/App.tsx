import { useState, useEffect, createContext, useContext, useCallback } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { api, AppConfig, getPin, setPin } from './api/client'
import Home from './pages/Home'
import Meals from './pages/Meals'
import CalendarPage from './pages/Calendar'
import Recipes from './pages/Recipes'
import Shopping from './pages/Shopping'

// --- Auth context ---

interface AuthCtx {
  pin: string
  config: AppConfig | null
  logout: () => void
}

const AuthContext = createContext<AuthCtx>({ pin: '', config: null, logout: () => {} })
export const useAuth = () => useContext(AuthContext)

// --- PIN screen ---

function PinScreen({ onAuth }: { onAuth: (pin: string) => void }) {
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [selected, setSelected] = useState<1 | 2 | null>(null)
  const [pin, setPinInput] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    api.config.get().then(setConfig).catch(() => {})
  }, [])

  function handleSubmit() {
    if (!pin.trim()) return
    setError('')
    onAuth(pin.trim())
  }

  return (
    <div className="pin-screen">
      <div style={{ fontSize: 40, marginBottom: 16 }}>🏠</div>
      <h1>HomeTogether</h1>
      <p>Enter your PIN to continue</p>

      {config && (
        <div className="user-buttons">
          <button
            className={`user-btn${selected === 1 ? ' selected' : ''}`}
            onClick={() => setSelected(1)}
          >
            {config.user1_name}
          </button>
          <button
            className={`user-btn${selected === 2 ? ' selected' : ''}`}
            onClick={() => setSelected(2)}
          >
            {config.user2_name}
          </button>
        </div>
      )}

      {selected && (
        <>
          <input
            className="form-input"
            type="password"
            inputMode="numeric"
            placeholder="PIN"
            value={pin}
            onChange={e => setPinInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleSubmit() }}
            autoFocus
            style={{ marginBottom: 12, textAlign: 'center', letterSpacing: 8, fontSize: 20 }}
          />
          {error && <p style={{ color: 'var(--accent-red)', fontSize: 13, marginBottom: 12 }}>{error}</p>}
          <button className="btn-primary" style={{ width: '100%' }} onClick={handleSubmit}>
            Continue
          </button>
        </>
      )}
    </div>
  )
}

// --- Tab bar ---

const tabs = [
  {
    path: '/calendar',
    label: 'Calendar',
    icon: (active: boolean) => (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <rect x="3" y="4" width="14" height="13" rx="2" stroke={active ? '#4A3F35' : '#A89880'} strokeWidth="1.5" />
        <path d="M3 8h14M7 2v4M13 2v4" stroke={active ? '#4A3F35' : '#A89880'} strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    path: '/meals',
    label: 'Meals',
    icon: (active: boolean) => (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M6 4h8M5 8h10M4 12h12M6 16h8" stroke={active ? '#4A3F35' : '#A89880'} strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    path: '/',
    label: 'Home',
    icon: (active: boolean) => (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M3 10l7-7 7 7M5 8.5V16a1 1 0 001 1h8a1 1 0 001-1V8.5" stroke={active ? '#4A3F35' : '#A89880'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    path: '/recipes',
    label: 'Recipes',
    icon: (active: boolean) => (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="8" r="4" stroke={active ? '#4A3F35' : '#A89880'} strokeWidth="1.5" />
        <path d="M4 17a6 6 0 0112 0" stroke={active ? '#4A3F35' : '#A89880'} strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    path: '/shopping',
    label: 'Shopping',
    icon: (active: boolean) => (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M5 10l3 3 7-7" stroke={active ? '#4A3F35' : '#A89880'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <rect x="3" y="3" width="14" height="14" rx="2" stroke={active ? '#4A3F35' : '#A89880'} strokeWidth="1.5" />
      </svg>
    ),
  },
]

function TabBar() {
  return (
    <nav className="tab-bar">
      {tabs.map(tab => (
        <NavLink
          key={tab.path}
          to={tab.path}
          end={tab.path === '/'}
          className={({ isActive }) => `tab-item${isActive ? ' active' : ''}`}
        >
          {({ isActive }) => (
            <>
              {tab.icon(isActive)}
              <span>{tab.label}</span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

// --- Main app shell ---

function AppShell() {
  return (
    <div className="app-shell">
      <div className="screen">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/meals" element={<Meals />} />
          <Route path="/calendar" element={<CalendarPage />} />
          <Route path="/recipes" element={<Recipes />} />
          <Route path="/shopping" element={<Shopping />} />
        </Routes>
      </div>
      <TabBar />
    </div>
  )
}

// --- Root ---

export default function App() {
  const [pin, setPinState] = useState(getPin)
  const [config, setConfig] = useState<AppConfig | null>(null)

  useEffect(() => {
    api.config.get().then(setConfig).catch(() => {})
  }, [])

  const handleAuth = useCallback((p: string) => {
    setPin(p)
    setPinState(p)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('ht_pin')
    setPinState('')
  }, [])

  useEffect(() => {
    const handler = () => { localStorage.removeItem('ht_pin'); setPinState('') }
    window.addEventListener('ht:unauthorized', handler)
    return () => window.removeEventListener('ht:unauthorized', handler)
  }, [])

  if (!pin) {
    return (
      <div className="app-shell">
        <PinScreen onAuth={handleAuth} />
      </div>
    )
  }

  return (
    <AuthContext.Provider value={{ pin, config, logout }}>
      <BrowserRouter>
        <AppShell />
      </BrowserRouter>
    </AuthContext.Provider>
  )
}
