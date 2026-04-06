// Integrations.jsx - Manage connected services

import { useState, useEffect } from 'react'

// Brand colors and logos
const BRAND_COLORS = {
  gmail: '#EA4335',
  google_calendar: '#4285F4',
  google_drive: '#0F9D58',
  google_business: '#4285F4',
  quickbooks: '#2CA01C',
  notion: '#000000',
  hubspot: '#FF7A59',
  slack: '#4A154B',
  square: '#000000',
  zoho: '#E42C14',
}

// Simple SVG logos inline
const BRAND_LOGOS = {
  gmail: <svg viewBox="0 0 24 24" width="28" height="28" fill="#EA4335"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm-1.5 17.5v-11.25l8.25 5.625-8.25 5.625z"/></svg>,
  google_calendar: <svg viewBox="0 0 24 24" width="28" height="28" fill="#4285F4"><path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zM9 14H7v-2h2v2zm4 0h-2v-2h2v2zm4 0h-2v-2h2v2zm-8 4H7v-2h2v2zm4 0h-2v-2h2v2zm4 0h-2v-2h2v2z"/></svg>,
  google_drive: <svg viewBox="0 0 87.3 78" width="28" height="28"><path fill="#0F9D58" d="m6.6 66.85 3.85 6.65c.8 1.4 1.95 2.5 3.3 3.3l13.75-23.8H1c0 1.55.4 3.1 1.2 4.5z"/><path fill="#FBBC04" d="M43.65 25.15 29.9 1.35C28.55 2.15 27.4 3.25 26.6 4.65l-25.4 44c-.8 1.4-1.2 2.95-1.2 4.5h27.5z"/><path fill="#4285F4" d="m73.55 76.8 13.75-23.8H57.9l-13.75 23.8c1.35.8 2.9 1.2 4.45 1.2h20.5c1.55 0 3.1-.4 4.45-1.2z"/><path fill="#0F9D58" d="M57.9 25.15 71.65 1.35 43.65 25.15z"/><path fill="#EA4335" d="m43.65 25.15 13.75-23.8H57.9z"/></svg>,
  google_business: <svg viewBox="0 0 24 24" width="28" height="28" fill="#4285F4"><path d="M12 7V3H2v18h20V7H12zM6 19H4v-2h2v2zm0-4H4v-2h2v2zm0-4H4V9h2v2zm0-4H4V5h2v2zm4 12H8v-2h2v2zm0-4H8v-2h2v2zm0-4H8V9h2v2zm0-4H8V5h2v2zm10 12h-8v-2h2v-2h-2v-2h2v-2h-2V9h8v10zm-2-8h-2v2h2v-2zm0 4h-2v2h2v-2z"/></svg>,
  quickbooks: <svg viewBox="0 0 24 24" width="28" height="28" fill="#2CA01C"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15h2v-6h-2v6zm0-8h2V7h-2v2z"/></svg>,
  notion: <svg viewBox="0 0 100 100" width="28" height="28"><rect width="100" height="100" rx="15" fill="#000"/><path d="M25 20h50v60H25z" fill="#fff"/><path d="M35 45h30v5H35zM35 55h30v5H35zM35 65h20v5H35z" fill="#000"/></svg>,
  hubspot: <svg viewBox="0 0 24 24" width="28" height="28" fill="#FF7A59"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="8" r="2" fill="#fff"/><circle cx="8" cy="14" r="2" fill="#fff"/><circle cx="16" cy="14" r="2" fill="#fff"/></svg>,
  slack: <svg viewBox="0 0 24 24" width="28" height="28" fill="#4A154B"><path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z"/></svg>,
  square: <svg viewBox="0 0 24 24" width="28" height="28" fill="#000"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>,
  zoho: <svg viewBox="0 0 24 24" width="28" height="28" fill="#E42C14"><circle cx="12" cy="12" r="10"/><path fill="#fff" d="M8 8h8v8H8z"/></svg>,
}

const AVAILABLE_INTEGRATIONS = [
  // Google
  { provider: 'gmail', label: 'Gmail', category: 'Google', scopes: 'Read/send emails' },
  { provider: 'google_calendar', label: 'Google Calendar', category: 'Google', scopes: 'Calendar events' },
  { provider: 'google_drive', label: 'Google Drive', category: 'Google', scopes: 'File storage' },
  { provider: 'google_business', label: 'Google Business', category: 'Google', scopes: 'Business profile' },
  // Business
  { provider: 'quickbooks', label: 'QuickBooks', category: 'Finance', scopes: 'Invoices, payments' },
  { provider: 'notion', label: 'Notion', category: 'Productivity', scopes: 'Notes, docs' },
  // Coming soon
  { provider: 'hubspot', label: 'HubSpot', category: 'CRM', scopes: 'CRM (coming soon)', disabled: true },
  { provider: 'slack', label: 'Slack', category: 'Communication', scopes: 'Messages (coming soon)', disabled: true },
  { provider: 'square', label: 'Square', category: 'Finance', scopes: 'Payments (coming soon)', disabled: true },
  { provider: 'zoho', label: 'Zoho CRM', category: 'CRM', scopes: 'CRM (coming soon)', disabled: true },
]

export default function Integrations() {
  const [integrations, setIntegrations] = useState({})
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState('')
  const [connecting, setConnecting] = useState(null)

  // Handle OAuth callback params
  useEffect(() => {
    setTimeout(() => {
      const params = new URLSearchParams(window.location.search)
      const connected = params.get('connected')
      const error = params.get('error')
      
      if (connected) {
        setToast(`✅ ${connected} connected successfully!`)
        window.history.replaceState({}, '', '/integrations')
        setTimeout(() => setToast(''), 5000)
        loadIntegrations()
      } else if (error) {
        setToast(`❌ ${error.replace(/_/g, ' ')}`)
        window.history.replaceState({}, '', '/integrations')
        setTimeout(() => setToast(''), 5000)
      }
    }, 100)
  }, [])

  const loadIntegrations = async () => {
    const userId = localStorage.getItem('user_id')
    const token = localStorage.getItem('token')
    
    try {
      const res = await fetch(`/api/integrations/list?user_id=${userId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        const map = {}
        data.forEach(i => { map[i.provider] = i })
        setIntegrations(map)
      }
    } catch (e) {
      console.error('Failed to load integrations:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadIntegrations()
  }, [])

  const handleConnect = async (provider) => {
    if (connecting) return
    setConnecting(provider)
    
    const userId = localStorage.getItem('user_id')
    window.location.href = `/api/auth/${provider}/connect?user_id=${userId}`
  }

  const handleDisconnect = async (provider) => {
    if (!confirm(`Disconnect ${provider}? You can reconnect later.`)) return
    
    const userId = localStorage.getItem('user_id')
    const token = localStorage.getItem('token')
    
    try {
      const res = await fetch(`/api/integrations/${provider}/disconnect`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ user_id: userId })
      })
      
      if (res.ok) {
        setToast(`🔌 ${provider} disconnected`)
        loadIntegrations()
      } else {
        setToast('❌ Failed to disconnect')
      }
    } catch (e) {
      setToast('❌ Error disconnecting')
    }
    setTimeout(() => setToast(''), 3000)
  }

  // Group by category
  const categories = [...new Set(AVAILABLE_INTEGRATIONS.map(i => i.category))]
  
  return (
    <div style={styles.container}>
      {toast && (
        <div style={{
          position: 'fixed', top: 20, right: 20,
          background: toast.startsWith('✅') ? '#10B981' : toast.startsWith('🔌') ? '#3B82F6' : '#EF4444',
          color: 'white', padding: '12px 20px', borderRadius: 8,
          zIndex: 9999, boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          fontWeight: 500
        }}>
          {toast}
        </div>
      )}
      
      {/* Header */}
      <div style={styles.header}>
        <div>
          <a href="/dashboard" style={styles.back}>← Back to Dashboard</a>
          <div style={styles.title}>Integrations</div>
          <div style={styles.subtitle}>Connect your accounts to enable AI capabilities</div>
        </div>
      </div>

      {loading ? (
        <div style={styles.loading}>Loading...</div>
      ) : (
        <div style={styles.content}>
          {categories.map(category => (
            <div key={category} style={styles.category}>
              <h3 style={styles.categoryTitle}>{category}</h3>
              <div style={styles.grid}>
                {AVAILABLE_INTEGRATIONS.filter(i => i.category === category).map(integration => {
                  const connected = integrations[integration.provider]?.connected
                  const Logo = BRAND_LOGOS[integration.provider]
                  const brandColor = BRAND_COLORS[integration.provider]
                  return (
                    <div key={integration.provider} style={{
                      ...styles.card,
                      opacity: integration.disabled ? 0.5 : 1
                    }}>
                      <div style={styles.cardHeader}>
                        <span style={{...styles.logoWrapper, background: brandColor + '15'}}>
                          {Logo}
                        </span>
                        <span style={styles.label}>{integration.label}</span>
                      </div>
                      <div style={styles.scopes}>{integration.scopes}</div>
                      <div style={styles.cardFooter}>
                        {integration.disabled ? (
                          <span style={styles.comingSoon}>Coming Soon</span>
                        ) : connected ? (
                          <>
                            <span style={styles.connectedBadge}>✅ Connected</span>
                            <button 
                              onClick={() => handleDisconnect(integration.provider)}
                              style={styles.disconnectBtn}
                            >
                              Disconnect
                            </button>
                          </>
                        ) : (
                          <button 
                            onClick={() => handleConnect(integration.provider)}
                            style={styles.connectBtn}
                            disabled={connecting === integration.provider}
                          >
                            {connecting === integration.provider ? 'Connecting...' : 'Connect'}
                          </button>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const styles = {
  container: {
    minHeight: '100vh',
    background: '#0f172a',
    color: '#e2e8f0',
    padding: '0 0 40px 0',
  },
  header: {
    padding: '30px 40px',
    borderBottom: '1px solid #1e293b',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  back: {
    color: '#64748b',
    textDecoration: 'none',
    fontSize: 14,
    display: 'block',
    marginBottom: 8,
  },
  title: {
    fontSize: 28,
    fontWeight: 700,
    marginBottom: 4,
  },
  subtitle: {
    color: '#64748b',
    fontSize: 14,
  },
  content: {
    padding: '30px 40px',
    maxWidth: 1200,
    margin: '0 auto',
  },
  category: {
    marginBottom: 32,
  },
  categoryTitle: {
    fontSize: 18,
    fontWeight: 600,
    marginBottom: 16,
    color: '#94a3b8',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: 16,
  },
  card: {
    background: '#1e293b',
    borderRadius: 12,
    padding: 20,
    border: '1px solid #334155',
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    marginBottom: 8,
  },
  icon: {
    fontSize: 24,
  },
  logoWrapper: {
    width: 40,
    height: 40,
    borderRadius: 8,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  label: {
    fontSize: 16,
    fontWeight: 600,
  },
  scopes: {
    fontSize: 13,
    color: '#64748b',
    marginBottom: 16,
  },
  cardFooter: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  connectedBadge: {
    fontSize: 13,
    color: '#10B981',
    fontWeight: 500,
  },
  connectBtn: {
    background: '#3b82f6',
    color: 'white',
    border: 'none',
    padding: '8px 16px',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
  },
  disconnectBtn: {
    background: 'transparent',
    color: '#ef4444',
    border: '1px solid #ef4444',
    padding: '6px 12px',
    borderRadius: 6,
    fontSize: 12,
    cursor: 'pointer',
  },
  comingSoon: {
    fontSize: 12,
    color: '#64748b',
    fontStyle: 'italic',
  },
  loading: {
    textAlign: 'center',
    padding: 60,
    color: '#64748b',
  },
}