import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Layout({ children }) {
  const { user, guest, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/')
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink to={user ? '/dashboard' : '/plan'} className="brand">
          ✈️ Yatra AI
        </NavLink>
        {user ? (
          <nav className="topnav">
            <NavLink to="/plan">New Trip</NavLink>
            <NavLink to="/trips">My Trips</NavLink>
            <NavLink to="/profile">Profile</NavLink>
            <button className="btn btn-ghost" onClick={handleLogout}>
              Logout
            </button>
          </nav>
        ) : (
          <nav className="topnav">
            {guest && <span className="guest-badge">Guest mode</span>}
            <NavLink to="/login">Log in</NavLink>
            <NavLink to="/register" className="btn btn-primary">
              Sign up to save trips
            </NavLink>
          </nav>
        )}
      </header>
      <main className="content">{children}</main>
    </div>
  )
}
