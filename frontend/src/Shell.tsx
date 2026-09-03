import { Navigate, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from './auth'

export function Shell() {
  const { user, loading, logout } = useAuth()

  if (loading) {
    return <p className="boot">Loading FleetLine…</p>
  }
  if (!user) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="app-shell">
      <aside>
        <p className="brand">
          FleetLine
          <span>{user.role}</span>
        </p>
        <nav>
          <NavLink to="/" end>
            Shipments
          </NavLink>
          <NavLink to="/book">Book</NavLink>
          <NavLink to="/quotes">Quotes</NavLink>
        </nav>
        <div className="who">
          <p>{user.full_name}</p>
          <p className="muted">{user.email}</p>
          <button type="button" className="linkish" onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>
      <main>
        <Outlet />
      </main>
    </div>
  )
}
