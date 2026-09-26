import { Link } from 'react-router-dom'

export default function Landing() {
  return (
    <div className="landing">
      <nav className="landing-nav">
        <span className="brand">✈️ Yatra AI</span>
        <div>
          <Link to="/plan" className="btn btn-primary">Start planning</Link>
        </div>
      </nav>

      <section className="hero">
        <h1>
          Your personal AI <span className="accent">travel agent</span>
        </h1>
        <p className="hero-sub">
          Describe your trip in plain words — real budgets, live weather,
          actual places — and get a feasible, personalized itinerary that
          adapts when your plans change.
        </p>
        <div className="hero-cta">
          <Link to="/plan" className="btn btn-primary btn-lg">
            Plan my trip →
          </Link>
          <Link to="/trips" className="btn btn-ghost btn-lg">
            My saved trips
          </Link>
        </div>

        <div className="demo-prompt">
          "Plan a 5-day trip from Delhi for 2 people under ₹50,000,
          focused on nature and food, with a relaxed itinerary."
        </div>

        <div className="feature-grid">
          <div className="feature-card">
            <h3>💰 Budget-aware</h3>
            <p>Every plan reconciles to your budget — never silently over.</p>
          </div>
          <div className="feature-card">
            <h3>🔍 Grounded</h3>
            <p>Live weather, real places, verified routes — not guesses.</p>
          </div>
          <div className="feature-card">
            <h3>🔄 Adaptive</h3>
            <p>Rain on day 2? Budget cut? The plan rebuilds around changes.</p>
          </div>
        </div>
      </section>
    </div>
  )
}
