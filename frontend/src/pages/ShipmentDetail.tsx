import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import type { ShipmentDetail, TrackingEvent } from '../types'

export function ShipmentDetailPage() {
  const { id } = useParams()
  const shipmentId = Number(id)
  const [shipment, setShipment] = useState<ShipmentDetail | null>(null)
  const [timeline, setTimeline] = useState<TrackingEvent[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    if (!Number.isFinite(shipmentId)) return
    Promise.all([api.getShipment(shipmentId), api.tracking(shipmentId)])
      .then(([detail, events]) => {
        setShipment(detail)
        setTimeline(events)
      })
      .catch((err: Error) => setError(err.message))
  }, [shipmentId])

  if (error) {
    return (
      <section>
        <p className="banner error">{error}</p>
        <Link to="/">Back to shipments</Link>
      </section>
    )
  }

  if (!shipment) {
    return <p className="muted">Loading shipment…</p>
  }

  return (
    <section>
      <p className="eyebrow">
        <Link to="/">Shipments</Link> / FL-{shipment.id}
      </p>
      <header className="page-head">
        <h1>{shipment.content}</h1>
        <span className={`pill status-${shipment.status}`}>
          {shipment.status.replaceAll('_', ' ')}
        </span>
      </header>

      <dl className="facts">
        <div>
          <dt>Customer</dt>
          <dd>{shipment.customer.full_name}</dd>
        </div>
        <div>
          <dt>Weight</dt>
          <dd>{shipment.weight_kg} kg</dd>
        </div>
        <div>
          <dt>Destination</dt>
          <dd>{shipment.destination}</dd>
        </div>
      </dl>

      <h2>Packages</h2>
      {shipment.packages.length === 0 ? (
        <p className="muted">No nested boxes on this booking.</p>
      ) : (
        <ul className="packages">
          {shipment.packages.map((box) => (
            <li key={box.id}>
              <strong>{box.description}</strong>
              <span>
                {box.weight_kg} kg · {box.length_cm}×{box.width_cm}×{box.height_cm} cm
              </span>
            </li>
          ))}
        </ul>
      )}

      <h2>Tracking</h2>
      {timeline.length === 0 ? (
        <p className="muted">No scans yet. Staff record these as the parcel moves.</p>
      ) : (
        <ol className="timeline">
          {timeline.map((event) => (
            <li key={event.id}>
              <span className={`pill status-${event.status}`}>
                {event.status.replaceAll('_', ' ')}
              </span>
              <div>
                <p>{event.location}</p>
                {event.note ? <p className="muted">{event.note}</p> : null}
                <time dateTime={event.recorded_at}>
                  {new Date(event.recorded_at).toLocaleString()}
                </time>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
