// Signup.jsx - Sign up page

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { provisionClient } from '../api'
import './Onboarding.css'

export default function Signup() {
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [verificationSent, setVerificationSent] = useState(false)
  const [userId, setUserId] = useState('')
  const [verificationCode, setVerificationCode] = useState('')

  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const res = await fetch('https://api.lipaira.ai/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, phone, password })
      })
      
      const data = await res.json()
      
      if (!res.ok) {
        throw new Error(data.error || 'Registration failed')
      }
      
      // Show verification screen
      setUserId(data.user_id)
      setVerificationSent(true)
    } catch (err) {
      let errorMsg = 'Signup failed. Please try again.'
      if (err instanceof Error) {
        errorMsg = err.message
      } else if (typeof err === 'object' && err !== null) {
        errorMsg = err.error || err.message || JSON.stringify(err)
      }
      setError(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  const handleVerify = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const res = await fetch('https://api.lipaira.ai/api/auth/verify-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, code: verificationCode })
      })
      
      const data = await res.json()
      
      if (!res.ok) {
        throw new Error(data.error || 'Verification failed')
      }
      
      // Save API key and redirect
      localStorage.setItem('lipaira_api_key', data.api_key)
      localStorage.setItem('user_id', data.user_id)
      navigate('/onboarding')
    } catch (err) {
      let errorMsg = 'Verification failed. Please try again.'
      if (err instanceof Error) {
        errorMsg = err.message
      }
      setError(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  // Verification screen
  if (verificationSent) {
    return (
      <div className="onboarding-container">
        <div className="onboarding-card">
          <div className="onboarding-logo">Lipaira</div>
          <h1 className="onboarding-heading">Verify your email</h1>
          <p style={{ color: '#666', marginBottom: '20px' }}>
            We sent a code to {email}
          </p>
          
          {error && <div className="onboarding-error">{error}</div>}
          
          <form onSubmit={handleVerify}>
            <input
              type="text"
              className="onboarding-input"
              placeholder="123456"
              value={verificationCode}
              onChange={e => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              maxLength={6}
              required
              style={{ textAlign: 'center', letterSpacing: '8px', fontSize: '24px' }}
            />
            <button type="submit" className="onboarding-button" disabled={loading || verificationCode.length !== 6}>
              {loading ? 'Verifying...' : 'Verify'}
            </button>
          </form>
          
          <p style={{ color: '#666', fontSize: '14px', marginTop: '20px' }}>
            Didn't receive code? <button onClick={() => {
              fetch('https://api.lipaira.ai/api/auth/resend-code', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId })
              })
            }} style={{ background: 'none', border: 'none', color: '#2563eb', cursor: 'pointer' }}>Resend</button>
          </p>
        </div>
      </div>
    )
  }

  // Original signup form
  return (
    <div className="onboarding-container">
      <div className="onboarding-card">
        <div className="onboarding-logo">Lipaira</div>
        <div className="onboarding-tagline">Your AI agent</div>
        
        <h1 className="onboarding-heading">
          Create your account
        </h1>
        
        {error && (
          <div className="onboarding-error">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <input
            type="email"
            className="onboarding-input"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
          />
          <input
            type="tel"
            className="onboarding-input"
            placeholder="Phone number"
            value={phone}
            onChange={e => setPhone(e.target.value)}
            required
          />
          <input
            type="password"
            className="onboarding-input"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
          />
          <button type="submit" className="onboarding-button" disabled={loading}>
            {loading ? 'Creating...' : 'Create account'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: '20px', color: '#6b7280', fontSize: '14px' }}>
          Already have an account?{' '}
          <a href="/login" style={{ color: '#2563eb', textDecoration: 'none' }}>Sign in</a>
        </p>
      </div>
    </div>
  )
}