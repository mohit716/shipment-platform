import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api'

export function BookPage() {
  const navigate = useNavigate()
  const [content, setContent] = useState('')
  const [weight, setWeight] = useState('2.4')
  const [destination, setDestination] = useState('11001')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const created = await api.book({
        content,
        weight_kg: Number(weight),
        destination: Number(destination),
      })
      navigate(`/shipments/${created.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not book.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="narrow">
      <p className="eyebrow">New booking</p>
      <h1>Book a shipment</h1>
      <p className="lede">
        The owner comes from your token, not from the form. Destination is a five-digit postcode.
      </p>
      <form onSubmit={onSubmit} className="stack">
        {error ? <p className="banner error">{error}</p> : null}
        <label>
          Contents
          <input
            value={content}
            onChange={(e) => setContent(e.target.value)}
            required
            minLength={3}
            placeholder="ceramic dinnerware, double boxed"
          />
        </label>
        <div className="split">
          <label>
            Weight (kg)
            <input
              type="number"
              step="0.1"
              min="0.1"
              max="25"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              required
            />
          </label>
          <label>
            Destination
            <input
              type="number"
              min="10000"
              max="99999"
              value={destination}
              onChange={(e) => setDestination(e.target.value)}
              required
            />
          </label>
        </div>
        <button type="submit" disabled={busy}>
          {busy ? 'Booking…' : 'Confirm booking'}
        </button>
      </form>
    </section>
  )
}
