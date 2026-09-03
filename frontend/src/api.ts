import type { FieldError, Quote, Shipment, ShipmentDetail, TrackingEvent, User } from './types'

const TOKEN_KEY = 'fleetline.token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  status: number
  details: FieldError[]

  constructor(status: number, message: string, details: FieldError[] = []) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

type Options = Omit<RequestInit, 'body'> & { body?: unknown }

async function request<T>(path: string, options: Options = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let body: BodyInit | undefined
  if (options.body instanceof URLSearchParams) {
    headers.set('Content-Type', 'application/x-www-form-urlencoded')
    body = options.body
  } else if (options.body !== undefined) {
    headers.set('Content-Type', 'application/json')
    body = JSON.stringify(options.body)
  }

  const response = await fetch(path, { ...options, headers, body })

  if (response.status === 204) {
    return undefined as T
  }

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(
      response.status,
      payload?.error?.message ?? response.statusText,
      payload?.error?.details ?? [],
    )
  }
  return payload as T
}

export const api = {
  login(email: string, password: string) {
    const body = new URLSearchParams()
    body.set('username', email)
    body.set('password', password)
    return request<{ access_token: string; token_type: string }>('/auth/token', {
      method: 'POST',
      body,
    })
  },

  me() {
    return request<User>('/auth/me')
  },

  register(body: { email: string; full_name: string; password: string }) {
    return request<User>('/users', { method: 'POST', body })
  },

  listShipments(status?: string) {
    const query = status ? `?status=${encodeURIComponent(status)}` : ''
    return request<Shipment[]>(`/shipments${query}`)
  },

  getShipment(id: number) {
    return request<ShipmentDetail>(`/shipments/${id}`)
  },

  book(body: {
    content: string
    weight_kg: number
    destination: number
    packages?: Array<{
      description: string
      weight_kg: number
      length_cm: number
      width_cm: number
      height_cm: number
    }>
  }) {
    return request<Shipment>('/shipments', { method: 'POST', body })
  },

  tracking(id: number) {
    return request<TrackingEvent[]>(`/shipments/${id}/tracking`)
  },

  quotes(weightKg: number) {
    return request<{
      weight_kg: number
      elapsed_seconds: number
      sequential_would_take: number
      quotes: Quote[]
    }>(`/shipments/quotes?weight_kg=${weightKg}`)
  },
}
