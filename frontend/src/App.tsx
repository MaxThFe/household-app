import { useState, useEffect, createContext, useContext, useCallback } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { api, AppConfig, getUser, setUser } from './api/client'
import Home from './pages/Home'
import Meals from './pages/Meals'
import CalendarPage from './pages/Calendar'
import Recipes from './pages/Recipes'
import Shopping from './pages/Shopping'

// --- Auth context ---

interface AuthCtx {
  user: string
  config: AppConfig | null
}

const AuthContext = createContext<AuthCtx>({ user: '', config: null })
export const useAuth = () => useContext(AuthContext)

// --- User select screen ---

function UserSelect({ onSelect }: { onSelect: (name: string) => void }) {
  const [config, setConfig] = useState<AppConfig | null>(null)

  useEffect(() => {
    api.config.get().then(setConfig).catch(() => {})
  }, [])

  const names = config ? [config.user1_name, config.user2_name] : ['Max', 'Margaux']

  return (
    <div className="pin-screen">
      <div style={{ fontSize: 40, marginBottom: 16 }}>🏠</div>
      <h1>HomeTogether</h1>
      <p>Who are you?</p>
      <div className="user-buttons">
        {names.map(name => (
          <button key={name} className="user-btn" onClick={() => onSelect(name)}>
            {name}
          </button>
        ))}
      </div>
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
        {/* Fork */}
        <path d="M7 2v3M9 2v3M7 5a1 1 0 002 0M8 6v9" stroke={active ? '#4A3F35' : '#A89880'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        {/* Knife */}
        <path d="M13 2c0 0 2 1.5 2 4h-2v9" stroke={active ? '#4A3F35' : '#A89880'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
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
        {/* Open book */}
        <path d="M10 16V5C10 5 8 3 4 3v13c4 0 6 2 6 2" stroke={active ? '#4A3F35' : '#A89880'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M10 16V5c0 0 2-2 6-2v13c-4 0-6 2-6 2" stroke={active ? '#4A3F35' : '#A89880'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
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
  const [user, setUserState] = useState(getUser)
  const [config, setConfig] = useState<AppConfig | null>(null)

  useEffect(() => {
    api.config.get().then(setConfig).catch(() => {})
  }, [])

  const handleSelect = useCallback((name: string) => {
    setUser(name)
    setUserState(name)
  }, [])

  useEffect(() => {
    const handler = () => { localStorage.removeItem('ht_user'); setUserState('') }
    window.addEventListener('ht:unauthorized', handler)
    return () => window.removeEventListener('ht:unauthorized', handler)
  }, [])

  if (!user) {
    return (
      <div className="app-shell">
        <UserSelect onSelect={handleSelect} />
      </div>
    )
  }

  return (
    <AuthContext.Provider value={{ user, config }}>
      <BrowserRouter>
        <AppShell />
      </BrowserRouter>
    </AuthContext.Provider>
  )
}
