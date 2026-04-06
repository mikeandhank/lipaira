// VerifyEmail.jsx - Standalone email verification page

import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

export default function VerifyEmail() {
  const location = useLocation()
  const navigate = useNavigate()
  
  const [userId, setUserId] = useState(location.state?.user_id || '')
  const [email, setEmail] = useState(location.state?.email || '')
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [resending, setResending] = useState(false)

  const handleVerify = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const res = await fetch('https://api.lipaira.ai/api/auth/verify-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, code })
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
      setError(err.message || 'Verification failed')
    } finally {
      setLoading(false)
    }
  }

  const handleResend = async () => {
    setResending(true)
    try {
      await fetch('https://api.lipaira.ai/api/auth/resend-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId })
      })
    } catch (e) {
      console.error('Resend failed:', e)
    }
    setResending(false)
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#f9fafb',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    }}>
      <div style={{
        background: 'white',
        padding: '40px',
        borderRadius: '12px',
        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
        width: '100%',
        maxWidth: '400px'
      }}>
        <div style={{ textAlign: 'center', marginBottom: '8px' }}>
          <div style={{ fontSize: '32px', fontWeight: '700', color: '#111' }}>Lipaira</div>
        </div>

        <h1 style={{ textAlign: 'center', fontSize: '24px', fontWeight: '600', margin: '24px 0' }}>
          Verify your email
        </h1>
        
        <p style={{ textAlign: 'center', color: '#6b7280', marginBottom: '24px' }}>
          We sent a code to {email || 'your email'}
        </p>

        {error && (
          <div style={{ background: '#fee2e2', color: '#dc2626', padding: '12px', borderRadius: '8px', marginBottom: '16px', fontSize: '14px' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleVerify}>
          <input
            type="text"
            value={code}
            onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            maxLength={6}
            required
            placeholder="123456"
            style={{
              width: '100%',
              padding: '16px',
              border: '1px solid #d1d5db',
              borderRadius: '8px',
              fontSize: '24px',
              textAlign: 'center',
              letterSpacing: '8px',
              marginBottom: '16px',
              boxSizing: 'border-box'
            }}
          />

          <button
            type="submit"
            disabled={loading || code.length !== 6}
            style={{
              width: '100%',
              padding: '14px',
              background: '#2563eb',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              fontSize: '16px',
              fontWeight: '600',
              cursor: (loading || code.length !== 6) ? 'not-allowed' : 'pointer',
              opacity: (loading || code.length !== 6) ? 0.7 : 1
            }}
          >
            {loading ? 'Verifying...' : 'Verify'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: '20px', color: '#6b7280', fontSize: '14px' }}>
          Didn't receive code?{' '}
          <button 
            onClick={handleResend} 
            disabled={resending}
            style={{ background: 'none', border: 'none', color: '#2563eb', cursor: 'pointer', fontWeight: '500' }}
          >
            {resending ? 'Sending...' : 'Resend'}
          </button>
        </p>
      </div>
    </div>
  )
}