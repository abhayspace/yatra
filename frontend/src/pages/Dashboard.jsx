import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { useAuth } from '../context/AuthContext'
import { supabase } from '../lib/supabase'

export default function Dashboard() {
  const { user, profile } = useAuth()
  const [trips, setTrips] = useState([])

  const displayName =
    profile?.full_name || user?.user_metadata?.full_name || user?.email || 'traveler'

  useEffect(() => {
    if (!user) return
    supabase
      .from('saved_trips')
      .select('id, trip_name, destination, start_date, created_at')
      .order('created_at', { ascending: false })
      .limit(4)
      .then(({ data }) => setTrips(data || []))
  }, [user])

  return (
    <Layout>
      <div className="dashboard">
        <h1>Hi {displayName.split(' ')[0]} 👋</h1>
        <p className="muted">Where would you like to go next?</p>

        <div className="action-grid">
          <Link to="/plan" className="action-card action-primary">
            <span className="action-icon">🗺️</span>
            <h3>Create New Trip</h3>
            <p>Describe your dream trip in plain words</p>
          </Link>
          <Link to="/trips" className="action-card">
            <span className="action-icon">📁</span>
            <h3>My Trips</h3>
            <p>View, edit or re-plan saved itineraries</p>
          </Link>
          <Link to="/profile" className="action-card">
            <span className="action-icon">⚙️</span>
            <h3>Travel Preferences</h3>
            <p>Set your budget, pace and interests</p>
          </Link>
        </div>

        {trips.length > 0 && (
          <>
            <h2 className="section-title">Recent trips</h2>
            <div className="trip-list">
              {trips.map((t) => (
                <Link key={t.id} to={`/trips/${t.id}`} className="trip-row">
                  <span className="trip-name">{t.trip_name}</span>
                  <span className="muted">
                    {t.destination || '—'} · {t.start_date || 'flexible dates'}
                  </span>
                </Link>
              ))}
            </div>
          </>
        )}
      </div>
    </Layout>
  )
}
