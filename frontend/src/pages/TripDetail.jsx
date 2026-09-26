import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import Layout from '../components/Layout'
import { useAuth } from '../context/AuthContext'
import { supabase } from '../lib/supabase'

export default function TripDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [trip, setTrip] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user) return
    supabase
      .from('saved_trips')
      .select('*')
      .eq('id', id)
      .maybeSingle()
      .then(({ data }) => {
        setTrip(data)
        setLoading(false)
      })
  }, [id, user])

  async function deleteTrip() {
    await supabase.from('saved_trips').delete().eq('id', id)
    navigate('/trips')
  }

  if (loading) {
    return (
      <Layout>
        <div className="page-center"><div className="spinner" /></div>
      </Layout>
    )
  }

  if (!trip) {
    return (
      <Layout>
        <div className="empty-state">
          <p>Trip not found.</p>
          <Link to="/trips" className="btn btn-ghost">← Back to trips</Link>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="trip-detail">
        <div className="trip-detail-head">
          <div>
            <h1>{trip.trip_name}</h1>
            <p className="muted">
              {trip.origin || '?'} → {trip.destination || '?'} ·{' '}
              {trip.travelers || '?'} travelers ·{' '}
              {trip.budget ? `₹${trip.budget}` : 'budget not set'}
            </p>
          </div>
          <div className="trip-actions">
            {trip.thread_id && (
              <Link
                to={`/plan?thread=${trip.thread_id}`}
                className="btn btn-primary"
              >
                🔄 Re-plan this trip
              </Link>
            )}
            <button className="btn btn-danger" onClick={deleteTrip}>
              Delete
            </button>
          </div>
        </div>
        <div className="msg msg-assistant itinerary">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {trip.itinerary || ''}
          </ReactMarkdown>
        </div>
      </div>
    </Layout>
  )
}
