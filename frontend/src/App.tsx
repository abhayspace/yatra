import { Navigate, Route, Routes } from 'react-router-dom'
import Landing from './pages/Landing'
import Planner from './pages/Planner'
import TripDetail from './pages/TripDetail'
import Trips from './pages/Trips'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/plan" element={<Planner />} />
      <Route path="/trips" element={<Trips />} />
      <Route path="/trips/:id" element={<TripDetail />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
