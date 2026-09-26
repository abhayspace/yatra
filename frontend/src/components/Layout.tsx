import { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink to="/plan" className="brand">
          ✈️ Yatra AI
        </NavLink>
        <nav className="topnav">
          <NavLink to="/plan">New Trip</NavLink>
          <NavLink to="/trips">My Trips</NavLink>
        </nav>
      </header>
      <main className="content">{children}</main>
    </div>
  )
}
