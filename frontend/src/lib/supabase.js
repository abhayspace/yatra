import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY

// Publishable key only — the secret/service key must never reach the client.
// Row Level Security policies enforce per-user data isolation.
export const supabase = createClient(supabaseUrl, supabaseKey)
