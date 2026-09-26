import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { listTrips } from '../lib/trips'

export default function Trips() {
  const trips = listTrips()

  return (
    <Layout>
      <div className="dashboard">
        <h1>My Trips</h1>
        {trips.length === 0 ? (
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
