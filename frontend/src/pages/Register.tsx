import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { ApiError } from '../api'
import { useAuth } from '../auth'

export function RegisterPage() {
  const { user, register } = useAuth()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/" replace />

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await register(email, fullName, password)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not register.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth-screen">
      <div className="auth-card">
        <p className="eyebrow">FleetLine</p>
        <h1>Create an account</h1>
        <p className="lede">New accounts are customers. Staff are promoted in the database.</p>
        <form onSubmit={onSubmit} className="stack">
          {error ? <p className="banner error">{error}</p> : null}
          <label>
            Full name
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              autoComplete="name"
              required
              minLength={2}
            />
          </label>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              required
              minLength={8}
              maxLength={72}
            />
          </label>
          <button type="submit" disabled={busy}>
            {busy ? 'Creating…' : 'Create account'}
          </button>
        </form>
        <p className="muted">
          Already booked with us? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </main>
  )
}
