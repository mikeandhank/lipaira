import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import './Onboarding.css'

export default function Onboarding() {
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const key = localStorage.getItem('lipaira_api_key')
    if (!key) {
      navigate('/signup')
      return
    }
    // Skip onboarding check - go directly to chat
    navigate('/chat')
  }, [navigate])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim() || loading) return

    setLoading(true)
    const key = localStorage.getItem('lipaira_api_key')
    
    // Save name locally for now (skipping server call)
    localStorage.setItem('user_name', name.trim())
    
    // Just redirect to chat
    navigate('/chat')
  }

  return (
    <div className="onboarding-container">
      <div className="onboarding-card">
        <div className="onboarding-logo">Lipaira</div>
        <div className="onboarding-tagline">Your AI agent</div>
        
        <h1 className="onboarding-heading">
          What should your agent call you?
        </h1>
        
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            className="onboarding-input"
            placeholder="Your name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
            disabled={loading}
          />
          
          <button
            type="submit"
            className="onboarding-button"
            disabled={!name.trim() || loading}
          >
            {loading ? 'Setting up...' : 'Start chatting →'}
          </button>
        </form>
      </div>
    </div>
  )
}