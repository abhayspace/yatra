import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { useAuth } from '../context/AuthContext'
import { supabase } from '../lib/supabase'

export default function Trips() {
  const { user } = useAuth()
  const [trips, setTrips] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user) return
    supabase
      .from('saved_trips')
      .select('id, trip_name, origin, destination, start_date, end_date, budget, created_at')
      .order('created_at', { ascending: false })
      .then(({ data }) => {
        setTrips(data || [])
        setLoading(false)
      })
  }, [user])

  return (
    <Layout>
      <div className="dashboard">
        <h1>My Trips</h1>
        {loading ? (
          <div className="spinner" />
        ) : trips.length === 0 ? (
          <div className="empty-state">
            <p>No saved trips yet.</p>
            <Link to="/plan" className="btn btn-primary">Plan your first trip</Link>
          </div>
        ) : (
          <div className="trip-list">
            {trips.map((t) => (
              <Link key={t.id} to={`/trips/${t.id}`} className="trip-row">
                <span className="trip-name">{t.trip_name}</span>
                <span className="muted">
                  {t.origin || '?'} → {t.destination || '?'} ·{' '}
                  {t.budget ? `₹${t.budget}` : 'no budget set'}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </Layout>
  )
}
