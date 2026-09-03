import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { Shipment, ShipmentStatus } from '../types'

const STATUSES: Array<ShipmentStatus | ''> = [
  '',
  'placed',
  'picked_up',
  'in_transit',
  'at_warehouse',
  'out_for_delivery',
  'delivered',
]

export function ShipmentsPage() {
  const [rows, setRows] = useState<Shipment[]>([])
  const [status, setStatus] = useState<ShipmentStatus | ''>('')
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .listShipments(status || undefined)
      .then(setRows)
      .catch((err: Error) => setError(err.message))
  }, [status])

  return (
    <section>
      <header className="page-head">
        <div>
          <p className="eyebrow">Operations</p>
          <h1>Shipments</h1>
        </div>
        <Link className="button" to="/book">
          Book a shipment
        </Link>
      </header>

      <label className="filter">
        Status
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as ShipmentStatus | '')}
        >
          <option value="">All</option>
          {STATUSES.filter(Boolean).map((value) => (
            <option key={value} value={value}>
              {value.replaceAll('_', ' ')}
            </option>
          ))}
        </select>
      </label>

      {error ? <p className="banner error">{error}</p> : null}

      {rows.length === 0 && !error ? (
        <p className="empty">No shipments in this view. Book one to populate the board.</p>
      ) : (
        <table className="grid">
          <thead>
            <tr>
              <th>Ref</th>
              <th>Contents</th>
              <th>Weight</th>
              <th>Destination</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <Link to={`/shipments/${row.id}`}>FL-{row.id}</Link>
                </td>
                <td>{row.content}</td>
                <td>{row.weight_kg} kg</td>
                <td>{row.destination}</td>
                <td>
                  <span className={`pill status-${row.status}`}>
                    {row.status.replaceAll('_', ' ')}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
