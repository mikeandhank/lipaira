import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const OAUTH_PROVIDERS = ['google', 'quickbooks', 'slack', 'notion', 'square', 'hubspot', 'pipedrive', 'salesforce', 'zoho']

const PROVIDERS = [
  { id: 'google', name: 'Google', icon: '🔵' },
  { id: 'microsoft', name: 'Microsoft', icon: '🟦' },
  { id: 'quickbooks', name: 'QuickBooks', icon: '🟢' },
  { id: 'slack', name: 'Slack', icon: '🟣' },
  { id: 'notion', name: 'Notion', icon: '⬛' },
  { id: 'square', name: 'Square', icon: '⬛' },
  { id: 'hubspot', name: 'HubSpot', icon: '🟠' },
  { id: 'pipedrive', name: 'Pipedrive', icon: '🟣' },
  { id: 'salesforce', name: 'Salesforce', icon: '🟦' },
  { id: 'zoho', name: 'Zoho', icon: '🟠' },
]

export default function Sidebar() {
  const navigate = useNavigate()
  const [credits, setCredits] = useState(0)
  const [connectedProviders, setConnectedProviders] = useState({})
  
  const userId = typeof window !== 'undefined' ? localStorage.getItem('user_id') : null
  const apiKey = typeof window !== 'undefined' ? localStorage.getItem('lipaira_api_key') : null
  
  useEffect(() => {
    if (!apiKey) return
    
    fetch('/api/credits', {
      headers: { 'X-Lipaira-Key': apiKey }
    })
    .then(r => r.json())
    .then(data => setCredits(data.credits || 0))
    .catch(() => {})
    
    Promise.all(
      OAUTH_PROVIDERS.map(provider =>
        fetch(`/api/auth/${provider}/status`, {
          headers: { 'X-User-ID': localStorage.getItem('user_id'), 'X-Lipaira-Key': apiKey }
        })
        .then(r => r.json())
        .then(data => ({ provider, connected: data.connected }))
        .catch(() => ({ provider, connected: false }))
      )
    ).then(results => {
      const statuses = {}
      results.forEach(r => { 
        if (r.connected) statuses[r.provider] = true 
      })
      setConnectedProviders(statuses)
    })
  }, [apiKey])
  
  const handleConnect = (provider) => {
    window.location.href = `https://lipaira.ai/api/auth/${provider}/connect?user_id=${userId}`
  }
  
  const handleAddCredits = async () => {
    try {
      const res = await fetch('/api/billing/credits/purchase', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-Lipaira-Key': apiKey
        },
        body: JSON.stringify({ amount: 25 })
      })
      const data = await res.json()
      if (data.checkout_url) {
        window.location.href = data.checkout_url
      } else if (data.url) {
        window.location.href = data.url
      } else {
        alert('Purchase failed: ' + (data.error || 'Unknown error'))
      }
    } catch (e) {
      alert('Failed to start purchase. Please try again.')
    }
  }
  
  const handleSignOut = () => {
    localStorage.clear()
    window.location.href = '/signup'
  }
  
  const getCreditColor = (val) => {
    if (val > 20) return '#22c55e'
    if (val >= 5) return '#f59e0b'
    return '#ef4444'
  }
  
  return (
    <div style={{
      width: '260px',
      height: '100vh',
      background: '#0f0f14',
      color: '#fff',
      padding: '20px 16px',
      position: 'fixed',
      left: 0,
      top: 0,
      overflowY: 'auto',
      borderRight: '1px solid #1a1a2e'
    }}>
      <div style={{
        fontSize: '22px',
        fontWeight: '700',
        background: 'linear-gradient(135deg, #6366f1, #a855f7)',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        marginBottom: '20px'
      }}>Lipaira</div>
      
      {/* Credits Section */}
      <div style={{
        background: '#16161e',
        borderRadius: '12px',
        padding: '16px',
        marginBottom: '20px'
      }}>
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px'}}>
          <span style={{fontSize: '12px', color: '#9ca3af'}}>CREDITS</span>
          <span style={{fontSize: '12px', color: '#9ca3af'}}>Balance</span>
        </div>
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
          <span style={{fontSize: '28px', fontWeight: 'bold', color: getCreditColor(credits)}}>
            ${credits.toFixed(2)}
          </span>
        </div>
        <button 
          onClick={handleAddCredits}
          style={{
            width: '100%',
            marginTop: '12px',
            padding: '10px',
            background: 'linear-gradient(135deg, #6366f1, #a855f7)',
            border: 'none',
            borderRadius: '8px',
            color: '#fff',
            cursor: 'pointer',
            fontWeight: '600'
          }}
        >
          + Add credits
        </button>
      </div>
      
      <div style={{height: '1px', background: '#1a1a2e', marginBottom: '20px'}} />
      
      {/* Navigation */}
      <div style={{marginBottom: '20px'}}>
        <div style={{fontSize: '12px', color: '#9ca3af', marginBottom: '10px'}}>MENU</div>
        <div 
          onClick={() => navigate('/dashboard')}
          style={{
            display: 'flex',
            alignItems: 'center',
            padding: '12px',
            borderRadius: '8px',
            cursor: 'pointer',
            background: '#6366f120',
            marginBottom: '4px',
          }}
        >
          <span style={{marginRight: '12px', fontSize: '18px'}}>📊</span>
          <span>Dashboard</span>
        </div>
        <div 
          onClick={() => navigate('/chat')}
          style={{
            display: 'flex',
            alignItems: 'center',
            padding: '12px',
            borderRadius: '8px',
            cursor: 'pointer',
            marginBottom: '4px',
          }}
        >
          <span style={{marginRight: '12px', fontSize: '18px'}}>💬</span>
          <span>Chat</span>
        </div>
      </div>
      
      {/* Integrations */}
      <div>
        <div style={{fontSize: '12px', color: '#9ca3af', marginBottom: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
          <span>INTEGRATIONS</span>
          <button 
            onClick={() => window.location.href = '/integrations'}
            style={{
              fontSize: '10px', 
              background: '#3b82f6', 
              border: 'none', 
              color: 'white', 
              padding: '2px 8px', 
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Manage
          </button>
        </div>
        {PROVIDERS.map(p => (
          <div 
            key={p.id}
            onClick={() => handleConnect(p.id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              padding: '12px',
              borderRadius: '8px',
              cursor: 'pointer',
              background: connectedProviders[p.id] ? '#10b98120' : 'transparent',
              marginBottom: '4px',
              border: connectedProviders[p.id] ? '1px solid #10b981' : '1px solid transparent'
            }}
          >
            <span style={{marginRight: '12px', fontSize: '18px'}}>{p.icon}</span>
            <span style={{flex: 1}}>{p.name}</span>
            {connectedProviders[p.id] && <span style={{color: '#10b981', fontSize: '12px'}}>✓ Connected</span>}
          </div>
        ))}
      </div>
      
      {/* Sign out */}
      <div style={{marginTop: 'auto', paddingTop: '20px'}}>
        <button 
          onClick={handleSignOut}
          style={{
            width: '100%',
            padding: '12px',
            background: 'transparent',
            border: '1px solid #374151',
            borderRadius: '8px',
            color: '#9ca3af',
            cursor: 'pointer'
          }}
        >
          Sign out
        </button>
      </div>
    </div>
  )
}
