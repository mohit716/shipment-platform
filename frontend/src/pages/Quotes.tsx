import { useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api'
import type { Quote } from '../types'

export function QuotesPage() {
  const [weight, setWeight] = useState('2.4')
  const [quotes, setQuotes] = useState<Quote[]>([])
  const [elapsed, setElapsed] = useState<number | null>(null)
  const [sequential, setSequential] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await api.quotes(Number(weight))
      setQuotes(result.quotes)
      setElapsed(result.elapsed_seconds)
      setSequential(result.sequential_would_take)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not quote.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="narrow">
      <p className="eyebrow">Rates</p>
      <h1>Compare carriers</h1>
      <p className="lede">
        The API asks every carrier at once. Elapsed time tracks the slowest call, not the sum.
      </p>
      <form onSubmit={onSubmit} className="inline-form">
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
        <button type="submit" disabled={busy}>
          {busy ? 'Asking carriers…' : 'Get quotes'}
        </button>
      </form>
      {error ? <p className="banner error">{error}</p> : null}
      {elapsed !== null && sequential !== null ? (
        <p className="muted">
          {elapsed}s elapsed · {sequential}s if asked one after another
        </p>
      ) : null}
      <ul className="quotes">
        {quotes.map((quote, index) => (
          <li key={quote.carrier} className={index === 0 ? 'best' : ''}>
            <strong>{quote.carrier}</strong>
            <span>£{quote.price.toFixed(2)}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
