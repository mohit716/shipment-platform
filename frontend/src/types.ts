export type UserRole = 'customer' | 'staff'

export type ShipmentStatus =
  | 'placed'
  | 'picked_up'
  | 'in_transit'
  | 'at_warehouse'
  | 'out_for_delivery'
  | 'delivered'
  | 'cancelled'
  | 'exception'

export type User = {
  id: number
  email: string
  full_name: string
  role: UserRole
  is_verified: boolean
  created_at: string
}

export type Package = {
  id: number
  description: string
  weight_kg: number
  length_cm: number
  width_cm: number
  height_cm: number
}

export type Warehouse = {
  id: number
  code: string
  name: string
  city: string
}

export type Tag = {
  id: number
  name: string
  requires_signature: boolean
}

export type TrackingEvent = {
  id: number
  status: ShipmentStatus
  location: string
  note: string | null
  recorded_at: string
}

export type Shipment = {
  id: number
  content: string
  weight_kg: number
  destination: number
  customer_id: number
  status: ShipmentStatus
}

export type ShipmentDetail = Shipment & {
  customer: { id: number; full_name: string }
  packages: Package[]
}

export type Quote = {
  carrier: string
  price: number
  latency: number
}

export type FieldError = { field: string; message: string }
