import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)

  async function loadProfile(userId) {
    const { data } = await supabase
      .from('users')
      .select('*')
      .eq('id', userId)
      .maybeSingle()
    setProfile(data)
  }

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      if (data.session?.user) loadProfile(data.session.user.id)
      setLoading(false)
    })

    const { data: listener } = supabase.auth.onAuthStateChange(
      (_event, newSession) => {
        setSession(newSession)
        if (newSession?.user) loadProfile(newSession.user.id)
        else setProfile(null)
      }
    )
    return () => listener.subscription.unsubscribe()
  }, [])

  // The backend performs username/password auth against Supabase and returns
  // a real Supabase session — adopt it so client-side queries carry RLS.
  async function adoptSession(sessionPayload) {
    await supabase.auth.setSession({
      access_token: sessionPayload.access_token,
      refresh_token: sessionPayload.refresh_token,
    })
    const { data } = await supabase.auth.getSession()
    setSession(data.session)
    if (data.session?.user) await loadProfile(data.session.user.id)
  }

  async function logout() {
    await supabase.auth.signOut()
    setSession(null)
    setProfile(null)
  }

  const value = {
    session,
    user: session?.user ?? null,
    profile,
    loading,
    adoptSession,
    logout,
    refreshProfile: () => session?.user && loadProfile(session.user.id),
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}
