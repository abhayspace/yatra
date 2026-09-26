import { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { useAuth } from '../context/AuthContext'
import { supabase } from '../lib/supabase'

export default function Profile() {
  const { user, profile, refreshProfile } = useAuth()
  const [fullName, setFullName] = useState('')
  const [prefs, setPrefs] = useState({
    preferred_budget: '',
    preferred_trip_style: '',
    food_preferences: '',
    accommodation_preferences: '',
    transportation_preferences: '',
    interests: '',
    preferred_pace: '',
  })
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (profile) setFullName(profile.full_name || '')
    if (!user) return
    supabase
      .from('travel_profiles')
      .select('*')
      .eq('user_id', user.id)
      .maybeSingle()
      .then(({ data }) => {
        if (data) {
          setPrefs({
            preferred_budget: data.preferred_budget ?? '',
            preferred_trip_style: data.preferred_trip_style ?? '',
            food_preferences: data.food_preferences ?? '',
            accommodation_preferences: data.accommodation_preferences ?? '',
            transportation_preferences: data.transportation_preferences ?? '',
            interests: (data.interests || []).join(', '),
            preferred_pace: data.preferred_pace ?? '',
          })
        }
      })
  }, [user, profile])

  async function save(e) {
    e.preventDefault()
    setMsg('')
    setBusy(true)

    const { error: userErr } = await supabase
      .from('users')
      .update({ full_name: fullName, updated_at: new Date().toISOString() })
      .eq('id', user.id)

    const interests = prefs.interests
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)

    const { error: prefErr } = await supabase
      .from('travel_profiles')
      .upsert(
        {
          user_id: user.id,
          ...prefs,
          preferred_budget: prefs.preferred_budget || null,
          interests,
          updated_at: new Date().toISOString(),
        },
        { onConflict: 'user_id' }
      )

    setBusy(false)
    if (userErr || prefErr) {
      setMsg(`Could not save: ${(userErr || prefErr).message}`)
    } else {
      setMsg('Saved ✓')
      refreshProfile()
    }
  }

  const field = (key, label, placeholder) => (
    <label key={key}>
      {label}
      <input
        value={prefs[key]}
        placeholder={placeholder}
        onChange={(e) => setPrefs({ ...prefs, [key]: e.target.value })}
      />
    </label>
  )

  return (
    <Layout>
      <div className="dashboard narrow">
        <h1>Profile & Travel Preferences</h1>
        <p className="muted">{user?.email}</p>

        {msg && <div className="alert alert-info">{msg}</div>}

        <form onSubmit={save} className="profile-form">
          <label>
            Full name
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </label>

          <h2 className="section-title">Travel preferences</h2>
          {field('preferred_budget', 'Typical budget (₹)', 'e.g. 50000')}
          {field('preferred_trip_style', 'Trip style', 'e.g. backpacking, luxury')}
          {field('preferred_pace', 'Preferred pace', 'relaxed / balanced / packed')}
          {field('food_preferences', 'Food preferences', 'e.g. vegetarian, street food')}
          {field('accommodation_preferences', 'Accommodation', 'e.g. hostel, 3-star')}
          {field('transportation_preferences', 'Transport', 'e.g. trains, flights')}
          {field('interests', 'Interests (comma separated)', 'nature, food, history')}

          <button className="btn btn-primary" disabled={busy}>
            {busy ? 'Saving…' : 'Save preferences'}
          </button>
        </form>
      </div>
    </Layout>
  )
}
