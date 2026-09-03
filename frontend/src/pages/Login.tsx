import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { ApiError } from '../api'
import { useAuth } from '../auth'

export function LoginPage() {
  const { user, login } = useAuth()
  const [email, setEmail] = useState('ada@example.com')
  const [password, setPassword] = useState('correct-horse')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/" replace />

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(email, password)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not sign in.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth-screen">
      <div className="auth-card">
        <p className="eyebrow">FleetLine</p>
        <h1>Sign in</h1>
        <p className="lede">Track bookings, scans and carrier rates from one desk.</p>
        <form onSubmit={onSubmit} className="stack">
          {error ? <p className="banner error">{error}</p> : null}
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          <button type="submit" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <p className="muted">
          New here? <Link to="/register">Create an account</Link>
        </p>
      </div>
    </main>
  )
}
