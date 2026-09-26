import { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../lib/api'

export default function ForgotPassword() {
  const [step, setStep] = useState(0)
  const [email, setEmail] = useState('')
  const [otp, setOtp] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  async function requestCode(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await apiFetch('/api/auth/forgot-password', {
        method: 'POST',
        body: { email: email.trim() },
      })
      setStep(1)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function submitReset(e) {
    e.preventDefault()
    setError('')
    if (password !== confirm) {
      setError('Passwords do not match')
      return
    }
    setBusy(true)
    try {
      await apiFetch('/api/auth/reset-password', {
        method: 'POST',
        body: { email: email.trim(), otp: otp.trim(), new_password: password },
      })
      setDone(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Reset password</h1>
        {error && <div className="alert alert-error">{error}</div>}

        {done ? (
          <>
            <div className="alert alert-info">
              Password updated. You can log in with your new password.
            </div>
            <Link to="/login" className="btn btn-primary btn-block">
              Go to login
            </Link>
          </>
        ) : step === 0 ? (
          <form onSubmit={requestCode}>
            <p className="muted">
              Enter your registered email — we'll send a reset code.
            </p>
            <label>
              Email address
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            <button className="btn btn-primary btn-block" disabled={busy}>
              {busy ? 'Sending…' : 'Send reset code'}
            </button>
          </form>
        ) : (
          <form onSubmit={submitReset}>
            <label>
              Reset code
              <input
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                required
                pattern="\d{6}"
                maxLength={6}
                className="otp-input"
              />
            </label>
            <label>
              New password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
            </label>
            <label>
              Confirm new password
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
                autoComplete="new-password"
              />
            </label>
            <button className="btn btn-primary btn-block" disabled={busy}>
              {busy ? 'Updating…' : 'Set new password'}
            </button>
          </form>
        )}

        <div className="auth-links">
          <Link to="/login">← Back to login</Link>
        </div>
      </div>
    </div>
  )
}
