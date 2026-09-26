import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Layout({ children }) {
  const { profile, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/')
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink to="/dashboard" className="brand">
          ✈️ Yatra AI
        </NavLink>
        <nav className="topnav">
          <NavLink to="/plan">New Trip</NavLink>
          <NavLink to="/trips">My Trips</NavLink>
          <NavLink to="/profile">Profile</NavLink>
          <button className="btn btn-ghost" onClick={handleLogout}>
            Logout
          </button>
        </nav>
      </header>
      <main className="content">{children}</main>
    </div>
  )
}
