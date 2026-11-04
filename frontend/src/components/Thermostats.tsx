import { useState, useEffect, useRef } from 'react'
import { api, ThermostatState } from '../api/client'

const STEP = 0.5
const MIN_C = 4
const MAX_C = 30
// Taps settle for this long before going to the valve, so +++ is one write.
const SEND_AFTER_MS = 1200

/** Heating setpoints, one row per room with a valve. Renders nothing without any. */
export function Thermostats() {
  const [thermostats, setThermostats] = useState<ThermostatState[]>([])

  // The backend serves its own cached poll, so this is cheap to repeat.
  const load = () => api.thermostats.list().then(setThermostats).catch(() => {})

  useEffect(() => {
    load()
    const id = setInterval(load, 60_000)
    return () => clearInterval(id)
  }, [])

  if (thermostats.length === 0) return null

  return (
    <div style={{ marginBottom: 20 }}>
      <p className="section-label">Heating</p>
      <div className="list-card">
        {thermostats.map(t => <ThermostatRow key={t.mac} thermostat={t} onSent={load} />)}
      </div>
    </div>
  )
}

function ThermostatRow({ thermostat: t, onSent }: { thermostat: ThermostatState; onSent: () => void }) {
  // What the person has dialled in but the valve has not confirmed yet; the
  // polled target only shows again once this is cleared.
  const [draft, setDraft] = useState<number | null>(null)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => () => clearTimeout(timer.current), [])

  // A sent draft stands until the poll reports it back.
  useEffect(() => {
    if (!sending && draft !== null && draft === t.target_temperature) setDraft(null)
  }, [t.target_temperature, sending])

  const target = draft ?? t.target_temperature

  const send = (value: number) => {
    setSending(true)
    api.thermostats.setTarget(t.room, value)
      .then(() => {
        setError(null)
        onSent()
      })
      .catch(() => {
        setError("Couldn't reach the valve")
        setDraft(null)
      })
      .finally(() => setSending(false))
  }

  const nudge = (delta: number) => {
    if (target === null) return
    const next = Math.min(MAX_C, Math.max(MIN_C, Math.round((target + delta) / STEP) * STEP))
    setDraft(next)
    setError(null)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => send(next), SEND_AFTER_MS)
  }

  const disabled = sending || target === null

  return (
    <div className="list-row" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: 14, fontWeight: 500 }}>{t.room}</p>
        <p style={{ fontSize: 11, color: error ? 'var(--accent-red)' : 'var(--text-muted)', marginTop: 2 }}>
          {error
            ?? (sending ? 'Setting…'
              : !t.reachable ? 'Valve out of reach'
              : t.current_temperature !== null ? `${t.current_temperature.toFixed(1)}° at the radiator`
              : '–')}
          {t.battery != null && t.battery < 10 && ` · battery ${t.battery}%`}
        </p>
      </div>
      <StepButton label="Lower" disabled={disabled} onClick={() => nudge(-STEP)}>−</StepButton>
      <p style={{
        width: 52,
        textAlign: 'center',
        fontSize: 18,
        fontWeight: 500,
        color: t.stale || draft !== null ? 'var(--text-muted)' : 'var(--text-primary)',
      }}>
        {target !== null ? `${target.toFixed(1)}°` : '–'}
      </p>
      <StepButton label="Raise" disabled={disabled} onClick={() => nudge(STEP)}>+</StepButton>
    </div>
  )
}

function StepButton({ label, disabled, onClick, children }: {
  label: string
  disabled: boolean
  onClick: () => void
  children: string
}) {
  return (
    <button
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      style={{
        width: 32,
        height: 32,
        borderRadius: '50%',
        background: 'var(--bg-inactive)',
        color: 'var(--text-primary)',
        fontSize: 18,
        lineHeight: 1,
        opacity: disabled ? 0.4 : 1,
      }}
    >
      {children}
    </button>
  )
}
