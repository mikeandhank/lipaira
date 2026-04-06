// Dashboard.jsx - Full billing dashboard per spec v3

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getBillingStatus, getAgents, hireAgent, fireAgent } from '../api'
import IntegrationCard from '../components/IntegrationCard'

const AGENT_TYPES = [
  { type: 'primary', name: 'Primary Agent', daily: 0.30 },
  { type: 'finance', name: 'Finance Agent', daily: 0.63 },
  { type: 'marketing', name: 'Marketing Agent', daily: 0.63 },
  { type: 'operations', name: 'Operations Agent', daily: 0.63 },
  { type: 'sales', name: 'Sales Agent', daily: 1.30 },
]

export default function Dashboard() {
  const [billing, setBilling] = useState(null)
  const [agents, setAgents] = useState({ agents: [], active_count: 0, total_daily: 0 })
  const [integrations, setIntegrations] = useState([])
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState('')

  // Handle OAuth callback params
  useEffect(() => {
    setTimeout(() => {
      const params = new URLSearchParams(window.location.search)
      const connected = params.get('connected')
      const error = params.get('error')
      
      if (connected) {
        setToast(`✅ ${connected} connected successfully!`)
        window.history.replaceState({}, '', '/dashboard')
        setTimeout(() => setToast(''), 5000)
      } else if (error) {
        setToast(`❌ ${error.replace(/_/g, ' ')}`)
        window.history.replaceState({}, '', '/dashboard')
        setTimeout(() => setToast(''), 5000)
      }
    }, 100)
  }, [])
  const [hiring, setHiring] = useState(null)
  const [firing, setFiring] = useState(null)
  const [testingConnection, setTestingConnection] = useState(null)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  const loadData = async () => {
    try {
      const [billingData, agentsData] = await Promise.all([
        getBillingStatus(),
        getAgents()
      ])
      
      // Fetch integrations
      let integrationsData = []
      const userId = localStorage.getItem('user_id')
      try {
        const integRes = await fetch(`/api/integrations/list?user_id=${userId}`, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        })
        if (integRes.ok) {
          integrationsData = await integRes.json()
        }
      } catch (e) {
        console.error('Failed to load integrations:', e)
      }
      
      setBilling(billingData)
      setAgents(agentsData)
      setIntegrations(integrationsData)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleHire = async (agentType) => {
    setHiring(agentType)
    try {
      await hireAgent(agentType)
      await loadData()
    } catch (e) {
      setError(e.message)
    } finally {
      setHiring(null)
    }
  }

  const handleFire = async (agentType) => {
    if (!confirm(`Fire ${agentType} agent? Billing stops today, no refund for days already used.`)) {
      return
    }
    setFiring(agentType)
    try {
      await fireAgent(agentType)
      await loadData()
    } catch (e) {
      setError(e.message)
    } finally {
      setFiring(null)
    }
  }

  const handleLogout = () => {
    localStorage.clear()
    navigate('/signup')
  }

  // Integration handlers
  const handleConnectIntegration = async (provider) => {
    try {
      const token = localStorage.getItem('token')
      let url, method, headers = {}
      
      // OAuth providers use /api/auth/ (return 302 redirect)
      const oauthProviders = [
        // Google granular services
        'gmail', 'google_calendar', 'google_drive', 'google_business',
        // Other providers
        'quickbooks', 
        'notion', 'slack', 'square',
        'hubspot', 'pipedrive', 'salesforce', 'zoho'
      ]
      
      if (oauthProviders.includes(provider)) {
        const userId = localStorage.getItem('user_id')
        if (!userId) {
          alert('Please log out and log back in to refresh your session.')
          return
        }
        // These return 302 redirect to OAuth provider
        window.location.href = `/api/auth/${provider}/connect?user_id=${userId}`
        return
      }
      
      // API-key based providers (GoDaddy, Shopify, Squarespace) need modal input
      // For now, show alert since we need a modal
      if (provider === 'godaddy') {
        alert('GoDaddy: Enter your API Key and Secret in the connection form. This requires UI update.')
        return
      }
      if (provider === 'shopify') {
        alert('Shopify: Enter your store domain and access token. This requires UI update.')
        return
      }
      if (provider === 'squarespace') {
        alert('Squarespace: OAuth connection. This requires UI update.')
        return
      }
      
      // Fallback: try the integrations endpoint
      url = `/api/integrations/${provider}/connect`
      headers = { 'Authorization': `Bearer ${token}` }
      
      const res = await fetch(url, { method: 'POST', headers })
      const data = await res.json()
      
      if (data.url) {
        window.location.href = data.url
      } else if (data.authorization_url) {
        window.location.href = data.authorization_url
      } else if (data.auth_url) {
        window.location.href = data.auth_url
      } else if (data.error) {
        setError(data.error)
      }
    } catch (e) {
      setError(`Failed to connect ${provider}: ${e.message}`)
    }
  }

  const handleDisconnectIntegration = async (provider) => {
    if (!confirm(`Disconnect ${provider}? You'll need to reconnect to use it again.`)) {
      return
    }
    try {
      await fetch(`/api/integrations/${provider}/disconnect`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      })
      await loadData()
    } catch (e) {
      setError(`Failed to disconnect ${provider}: ${e.message}`)
    }
  }

  const handleTestIntegration = async (provider) => {
    setTestingConnection(provider)
    try {
      const res = await fetch(`/api/integrations/${provider}/test`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      })
      const data = await res.json()
      if (data.success) {
        alert(`${provider} connection is working!`)
      } else {
        alert(`Connection failed: ${data.error}`)
      }
    } catch (e) {
      alert(`Test failed: ${e.message}`)
    } finally {
      setTestingConnection(null)
    }
  }

  if (loading) {
    return <div style={styles.loading}>Loading...</div>
  }

  const balance = billing?.balance_usd || 0
  const burnRate = billing?.daily_burn_usd || 0
  const runway = billing?.runway_days || 0

  return (
    <div style={styles.container}>
      {toast && (
        <div style={{
          position: 'fixed', top: 20, right: 20,
          background: toast.startsWith('✅') ? '#10B981' : '#EF4444',
          color: 'white', padding: '12px 20px', borderRadius: 8,
          zIndex: 9999, boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          fontWeight: 500
        }}>
          {toast}
        </div>
      )}
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.logo}>Lipaira</div>
        <div style={styles.headerRight}>
          <button onClick={handleLogout} style={styles.logoutBtn}>Logout</button>
        </div>
      </div>

      <div style={styles.content}>
        {error && <div style={styles.error}>{error}</div>}

        {/* CREDIT BALANCE */}
        <div style={styles.balanceCard}>
          <div style={styles.balanceLabel}>CREDIT BALANCE</div>
          <div style={styles.balanceValue}>${balance.toFixed(2)}</div>
          <div style={styles.balanceButtons}>
            <button style={styles.addCreditsBtn}>+ Add Credits</button>
          </div>
          <div style={styles.balanceDetails}>
            <div>Daily burn rate: ~${burnRate.toFixed(2)}/day</div>
            <div>Estimated runway: {runway} days</div>
          </div>
        </div>

        {/* YOUR TEAM */}
        <div style={styles.teamCard}>
          <div style={styles.teamHeader}>
            <div style={styles.teamTitle}>YOUR TEAM</div>
            <button 
              onClick={() => navigate('/chat')}
              style={styles.chatLink}
            >
              Chat →
            </button>
          </div>

          {/* Active Agents */}
          {agents.agents.filter(a => a.status === 'active').map(agent => (
            <div key={agent.id} style={styles.agentRow}>
              <div style={styles.agentInfo}>
                <span style={styles.agentDot}>●</span>
                <span style={styles.agentName}>{agent.type} Agent</span>
              </div>
              <div style={styles.agentRight}>
                <span style={styles.agentRate}>${agent.daily_rate}/day</span>
                <span style={styles.agentStatus}>Active</span>
                <button 
                  onClick={() => handleFire(agent.type)}
                  disabled={firing === agent.type}
                  style={styles.fireBtn}
                >
                  {firing === agent.type ? '...' : 'Fire'}
                </button>
              </div>
            </div>
          ))}

          {/* Available to Hire */}
          {AGENT_TYPES.filter(a => !agents.agents.some(ag => ag.type === a.type && ag.status === 'active')).map(agent => (
            <div key={agent.type} style={styles.hireRow}>
              <div style={styles.agentInfo}>
                <span style={styles.hirePlus}>+</span>
                <span style={styles.hireName}>Hire {agent.name}</span>
              </div>
              <div style={styles.agentRight}>
                <span style={styles.hireRate}>${agent.daily}/day</span>
                <button 
                  onClick={() => handleHire(agent.type)}
                  disabled={hiring === agent.type}
                  style={styles.hireBtn}
                >
                  {hiring === agent.type ? '...' : 'Hire'}
                </button>
              </div>
            </div>
          ))}

          {agents.active_count === 0 && (
            <div style={styles.noAgents}>
              No agents hired yet. Hire one to get started!
            </div>
          )}

          {/* Active count summary */}
          {agents.active_count > 0 && (
            <div style={styles.teamSummary}>
              Total: {agents.active_count} agent{agents.active_count !== 1 ? 's' : ''} · ${agents.total_daily}/day
            </div>
          )}
        </div>

        {/* THIS WEEK */}
        <div style={styles.weekCard}>
          <div style={styles.weekTitle}>THIS WEEK</div>
          <div style={styles.weekNote}>
            {burnRate > 0 
              ? `You're spending ~$${(burnRate * 7).toFixed(2)}/week`
              : 'No spending this week yet'}
          </div>
          <div style={styles.chartPlaceholder}>
            <div style={styles.chartBars}>
              {[...Array(7)].map((_, i) => (
                <div key={i} style={{
                  ...styles.bar,
                  height: burnRate > 0 ? `${Math.random() * 60 + 20}%` : '10%',
                  background: burnRate > 0 ? 'var(--primary)' : 'var(--border)'
                }} />
              ))}
            </div>
            <div style={styles.chartLabels}>
              <span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span>
            </div>
          </div>
        </div>

        {/* INTEGRATIONS */}
        <div style={styles.integrationsCard}>
          <div style={styles.integrationsTitle}>INTEGRATIONS</div>
          <div style={styles.integrationList}>
            {integrations.length > 0 ? (
              integrations.map((integration) => (
                <IntegrationCard
                  key={integration.provider}
                  provider={integration.provider}
                  label={integration.provider.charAt(0).toUpperCase() + integration.provider.slice(1)}
                  status={integration.status || 'gray'}
                  detail={integration.detail}
                  connected={integration.status && integration.status !== 'gray'}
                  onConnect={() => handleConnectIntegration(integration.provider)}
                  onTest={() => handleTestIntegration(integration.provider)}
                  onDisconnect={() => handleDisconnectIntegration(integration.provider)}
                />
              ))
            ) : (
              // Fallback static list when no API data
              <>
                <IntegrationCard
                  provider="gmail"
                  label="Gmail"
                  status="green"
                  detail="Email & contacts"
                  connected={false}
                  onConnect={() => handleConnectIntegration('gmail')}
                  onTest={() => handleTestIntegration('gmail')}
                  onDisconnect={() => handleDisconnectIntegration('gmail')}
                />
                <IntegrationCard
                  provider="google_calendar"
                  label="Google Calendar"
                  status="green"
                  detail="Calendar events"
                  connected={false}
                  onConnect={() => handleConnectIntegration('google_calendar')}
                  onTest={() => handleTestIntegration('google_calendar')}
                  onDisconnect={() => handleDisconnectIntegration('google_calendar')}
                />
                <IntegrationCard
                  provider="google_drive"
                  label="Google Drive"
                  status="green"
                  detail="File storage"
                  connected={false}
                  onConnect={() => handleConnectIntegration('google_drive')}
                  onTest={() => handleTestIntegration('google_drive')}
                  onDisconnect={() => handleDisconnectIntegration('google_drive')}
                />
                <IntegrationCard
                  provider="google_business"
                  label="Google Business"
                  status="green"
                  detail="Business profile"
                  connected={false}
                  onConnect={() => handleConnectIntegration('google_business')}
                  onTest={() => handleTestIntegration('google_business')}
                  onDisconnect={() => handleDisconnectIntegration('google_business')}
                />
                <IntegrationCard
                  provider="quickbooks"
                  label="QuickBooks"
                  status="green"
                  detail="Dave's Plumbing"
                  connected={true}
                  onConnect={() => handleConnectIntegration('quickbooks')}
                  onTest={() => handleTestIntegration('quickbooks')}
                  onDisconnect={() => handleDisconnectIntegration('quickbooks')}
                />
                <IntegrationCard
                  provider="godaddy"
                  label="GoDaddy"
                  status="gray"
                  connected={false}
                  onConnect={() => handleConnectIntegration('godaddy')}
                />
                <IntegrationCard
                  provider="shopify"
                  label="Shopify"
                  status="gray"
                  connected={false}
                  onConnect={() => handleConnectIntegration('shopify')}
                />
              </>
            )}
          </div>
        </div>

        {/* SETTINGS */}
        <div style={styles.settingsCard}>
          <div style={styles.settingsTitle}>SETTINGS</div>
          <div style={styles.settingRow}>
            <span>Auto-refill</span>
            <span style={styles.settingOff}>OFF</span>
            <button style={styles.settingBtn}>Set</button>
          </div>
          <div style={styles.settingRow}>
            <span>Monthly spend cap</span>
            <span style={styles.settingOff}>OFF</span>
            <button style={styles.settingBtn}>Set</button>
          </div>
          <div style={styles.settingRow}>
            <span>Low balance alerts</span>
            <span style={styles.settingOn}>ON</span>
            <button style={styles.settingBtn}>Edit</button>
          </div>
        </div>
      </div>
    </div>
  )
}

const styles = {
  container: {
    minHeight: '100vh',
    background: 'var(--bg)',
  },
  loading: {
    color: 'var(--text-muted)',
    textAlign: 'center',
    paddingTop: '100px',
  },
  error: {
    background: '#fee',
    color: '#c00',
    padding: '12px',
    borderRadius: '8px',
    marginBottom: '16px',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 24px',
    borderBottom: '1px solid var(--border)',
    background: 'var(--card)',
  },
  logo: {
    fontSize: '20px',
    fontWeight: '700',
    color: 'var(--primary)',
  },
  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
  },
  logoutBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    fontSize: '14px',
    cursor: 'pointer',
  },
  content: {
    maxWidth: '600px',
    margin: '0 auto',
    padding: '24px 16px',
  },

  // Balance Card
  balanceCard: {
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    borderRadius: '16px',
    padding: '32px',
    marginBottom: '16px',
    color: '#fff',
  },
  balanceLabel: {
    fontSize: '12px',
    letterSpacing: '1px',
    opacity: 0.8,
    marginBottom: '8px',
  },
  balanceValue: {
    fontSize: '48px',
    fontWeight: '700',
    marginBottom: '16px',
  },
  balanceButtons: {
    marginBottom: '16px',
  },
  addCreditsBtn: {
    background: 'rgba(255,255,255,0.2)',
    border: '1px solid rgba(255,255,255,0.3)',
    borderRadius: '8px',
    color: '#fff',
    padding: '10px 20px',
    fontSize: '14px',
    cursor: 'pointer',
  },
  balanceDetails: {
    fontSize: '14px',
    opacity: 0.9,
    lineHeight: '1.6',
  },

  // Team Card
  teamCard: {
    background: 'var(--card)',
    borderRadius: '12px',
    padding: '20px',
    marginBottom: '16px',
    border: '1px solid var(--border)',
  },
  teamHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '16px',
  },
  teamTitle: {
    fontSize: '14px',
    fontWeight: '600',
    color: 'var(--text-muted)',
    letterSpacing: '1px',
  },
  chatLink: {
    background: 'none',
    border: 'none',
    color: 'var(--primary)',
    fontSize: '14px',
    cursor: 'pointer',
  },
  agentRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 0',
    borderBottom: '1px solid var(--border)',
  },
  agentInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  agentDot: {
    color: '#22c55e',
    fontSize: '10px',
  },
  agentName: {
    fontWeight: '500',
    textTransform: 'capitalize',
  },
  agentRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  agentRate: {
    color: 'var(--text-muted)',
    fontSize: '14px',
  },
  agentStatus: {
    color: '#22c55e',
    fontSize: '12px',
  },
  fireBtn: {
    background: 'transparent',
    border: '1px solid var(--border)',
    borderRadius: '6px',
    color: 'var(--text-muted)',
    padding: '6px 12px',
    fontSize: '12px',
    cursor: 'pointer',
  },
  hireRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 0',
    borderBottom: '1px solid var(--border)',
  },
  hirePlus: {
    color: 'var(--primary)',
    fontSize: '16px',
    fontWeight: '600',
  },
  hireName: {
    color: 'var(--text-muted)',
  },
  hireRate: {
    color: 'var(--text-muted)',
    fontSize: '14px',
  },
  hireBtn: {
    background: 'var(--primary)',
    border: 'none',
    borderRadius: '6px',
    color: '#fff',
    padding: '6px 12px',
    fontSize: '12px',
    cursor: 'pointer',
  },
  noAgents: {
    textAlign: 'center',
    color: 'var(--text-muted)',
    padding: '20px',
    fontSize: '14px',
  },
  teamSummary: {
    marginTop: '16px',
    paddingTop: '12px',
    borderTop: '1px solid var(--border)',
    fontSize: '14px',
    color: 'var(--text-muted)',
  },

  // Week Card
  weekCard: {
    background: 'var(--card)',
    borderRadius: '12px',
    padding: '20px',
    marginBottom: '16px',
    border: '1px solid var(--border)',
  },
  weekTitle: {
    fontSize: '14px',
    fontWeight: '600',
    color: 'var(--text-muted)',
    letterSpacing: '1px',
    marginBottom: '8px',
  },
  weekNote: {
    fontSize: '14px',
    color: 'var(--text-muted)',
    marginBottom: '16px',
  },
  chartPlaceholder: {
    height: '120px',
  },
  chartBars: {
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    height: '100px',
    gap: '8px',
  },
  bar: {
    flex: 1,
    borderRadius: '4px 4px 0 0',
    minHeight: '10px',
  },
  chartLabels: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '11px',
    color: 'var(--text-muted)',
    marginTop: '8px',
  },

  // Integrations Card
  integrationsCard: {
    background: 'var(--card)',
    borderRadius: '12px',
    padding: '20px',
    marginBottom: '16px',
    border: '1px solid var(--border)',
  },
  integrationsTitle: {
    fontSize: '14px',
    fontWeight: '600',
    color: 'var(--text-muted)',
    letterSpacing: '1px',
    marginBottom: '16px',
  },
  integrationList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  integrationItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  checkMark: {
    color: '#22c55e',
    fontWeight: '600',
  },
  integrationPending: {
    color: 'var(--border)',
    fontWeight: '600',
  },
  manageBtn: {
    marginLeft: 'auto',
    background: 'none',
    border: '1px solid var(--border)',
    borderRadius: '6px',
    color: 'var(--text-muted)',
    padding: '4px 12px',
    fontSize: '12px',
    cursor: 'pointer',
  },
  connectBtnSmall: {
    marginLeft: 'auto',
    background: 'var(--primary)',
    border: 'none',
    borderRadius: '6px',
    color: '#fff',
    padding: '4px 12px',
    fontSize: '12px',
    cursor: 'pointer',
  },

  // Settings Card
  settingsCard: {
    background: 'var(--card)',
    borderRadius: '12px',
    padding: '20px',
    border: '1px solid var(--border)',
  },
  settingsTitle: {
    fontSize: '14px',
    fontWeight: '600',
    color: 'var(--text-muted)',
    letterSpacing: '1px',
    marginBottom: '16px',
  },
  settingRow: {
    display: 'flex',
    alignItems: 'center',
    padding: '12px 0',
    borderBottom: '1px solid var(--border)',
  },
  settingOff: {
    marginLeft: 'auto',
    color: 'var(--text-muted)',
    fontSize: '12px',
  },
  settingOn: {
    marginLeft: 'auto',
    color: '#22c55e',
    fontSize: '12px',
  },
  settingBtn: {
    background: 'none',
    border: '1px solid var(--border)',
    borderRadius: '6px',
    color: 'var(--text-muted)',
    padding: '4px 12px',
    fontSize: '12px',
    marginLeft: '12px',
    cursor: 'pointer',
  },
}