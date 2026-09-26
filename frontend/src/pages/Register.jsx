import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import { useAuth } from '../context/AuthContext'

const STEPS = ['Details', 'Verify email']

export default function Register() {
  const [step, setStep] = useState(0)
  const [username, setUsername] = useState('')
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [otp, setOtp] = useState('')
  const [devOtp, setDevOtp] = useState('')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [busy, setBusy] = useState(false)
  const [cooldown, setCooldown] = useState(0)

  const { adoptSession, continueAsGuest } = useAuth()
  const navigate = useNavigate()

  function startCooldown() {
    setCooldown(60)
    const t = setInterval(() => {
      setCooldown((c) => {
        if (c <= 1) clearInterval(t)
        return c - 1
      })
    }, 1000)
  }

  async function submitDetails(e) {
    e.preventDefault()
    setError('')
    if (password !== confirm) {
      setError('Passwords do not match')
      return
    }
    setBusy(true)
    try {
      const data = await apiFetch('/api/auth/register', {
        method: 'POST',
        body: {
          username: username.trim(),
          full_name: fullName.trim(),
          email: email.trim(),
          password,
          confirm_password: confirm,
        },
      })
      if (data.dev_otp) setDevOtp(data.dev_otp)
      setInfo(data.message || 'Verification code sent.')
      setStep(1)
      startCooldown()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function submitOtp(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const { setup_token } = await apiFetch('/api/auth/verify-otp', {
        method: 'POST',
        body: { email: email.trim(), otp: otp.trim() },
      })
      // Password was collected in step 1 and held only in memory —
      // finalize the account now that the email is verified.
      const data = await apiFetch('/api/auth/setup-credentials', {
        method: 'POST',
        body: {
          setup_token,
          password,
          confirm_password: password,
        },
      })
      await adoptSession(data)
      navigate('/dashboard')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function resend() {
    setError('')
    try {
      const data = await apiFetch('/api/auth/resend-otp', {
        method: 'POST',
        body: { email: email.trim(), purpose: 'verify' },
      })
      if (data.dev_otp) setDevOtp(data.dev_otp)
      setInfo('A new code was sent.')
      startCooldown()
    } catch (err) {
      setError(err.message)
    }
  }

  function skip() {
    continueAsGuest()
    navigate('/plan')
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="steps">
          {STEPS.map((s, i) => (
            <span key={s} className={i <= step ? 'step active' : 'step'}>
              {i + 1}. {s}
            </span>
          ))}
        </div>

        <h1>Create your account</h1>

        {error && <div className="alert alert-error">{error}</div>}
        {info && <div className="alert alert-info">{info}</div>}
        {devOtp && (
          <div className="alert alert-dev">
            Email delivery unavailable — dev code: <b>{devOtp}</b>
          </div>
        )}

        {step === 0 && (
          <form onSubmit={submitDetails}>
            <label>
              Username
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                pattern="[A-Za-z0-9_]{3,20}"
                title="3–20 chars: letters, digits, underscore"
                autoComplete="username"
              />
            </label>
            <label>
              Full name
              <input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                minLength={2}
                autoComplete="name"
              />
            </label>
            <label>
              Email address
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </label>
            <label>
              Password
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
              Confirm password
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
                autoComplete="new-password"
              />
            </label>
            <p className="muted">
              Password: min 8 characters with letters and digits.
            </p>
            <button className="btn btn-primary btn-block" disabled={busy}>
              {busy ? 'Sending code…' : 'Continue'}
            </button>
          </form>
        )}

        {step === 1 && (
          <form onSubmit={submitOtp}>
            <p className="muted">
              We emailed a 6-digit code to <b>{email}</b>. It expires in 10
              minutes.
            </p>
            <label>
              Verification code
              <input
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                required
                inputMode="numeric"
                pattern="\d{6}"
                maxLength={6}
                placeholder="000000"
                className="otp-input"
              />
            </label>
            <button className="btn btn-primary btn-block" disabled={busy}>
              {busy ? 'Creating account…' : 'Verify & create account'}
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-block"
              onClick={resend}
              disabled={cooldown > 0}
            >
              {cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend code'}
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-block"
              onClick={() => setStep(0)}
            >
              ← Change details
            </button>
          </form>
        )}

        <div className="auth-links">
          <button type="button" className="linklike" onClick={skip}>
            Skip — explore as guest
          </button>
          <span>
            Already registered? <Link to="/login">Log in</Link>
          </span>
        </div>
      </div>
    </div>
  )
}
