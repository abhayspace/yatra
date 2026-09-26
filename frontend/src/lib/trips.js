const KEY = 'yatra_trips'

function read() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]')
  } catch {
    return []
  }
}

function write(trips) {
  localStorage.setItem(KEY, JSON.stringify(trips))
}

export function listTrips() {
  return read()
}

export function getTrip(id) {
  return read().find((t) => t.id === id) || null
}

export function saveTrip(trip) {
  const trips = read()
  trips.unshift({ ...trip, created_at: new Date().toISOString() })
  write(trips)
  return trip
}

export function deleteTrip(id) {
  write(read().filter((t) => t.id !== id))
}
