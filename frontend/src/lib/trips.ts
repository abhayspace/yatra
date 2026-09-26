export interface SavedTrip {
  id: string
  trip_name: string
  origin: string | null
  destination: string | null
  travelers: number | null
  budget: number | null
  itinerary: string
  thread_id: string | null
  created_at?: string
}

const KEY = 'yatra_trips'

function read(): SavedTrip[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]') as SavedTrip[]
  } catch {
    return []
  }
}

function write(trips: SavedTrip[]): void {
  localStorage.setItem(KEY, JSON.stringify(trips))
}

export function listTrips(): SavedTrip[] {
  return read()
}

export function getTrip(id: string): SavedTrip | null {
  return read().find((t) => t.id === id) ?? null
}

export function saveTrip(trip: SavedTrip): SavedTrip {
  const trips = read()
  trips.unshift({ ...trip, created_at: new Date().toISOString() })
  write(trips)
  return trip
}

export function deleteTrip(id: string): void {
  write(read().filter((t) => t.id !== id))
}
