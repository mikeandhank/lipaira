// api.js - All fetch calls in one place
// Adapted to work with Lipaira API

const BASE = ''  // Use relative URLs - nginx proxies /api/ to backend

function getKey() {
  return localStorage.getItem('lipaira_api_key')
}

export async function provisionClient(email, password) {
  // Use existing /api/auth/register endpoint
  const res = await fetch(`${BASE}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  })
  
  const data = await res.json()
  
  if (!res.ok) throw new Error(data.error || 'Signup failed')
  
  // Map to expected format - includes user_id for OAuth flows
  return {
    api_key: data.api_key,
    credits: data.credits,
    user: { id: data.user_id }
  }
}

export async function getMe() {
  const key = getKey()
  const res = await fetch(`${BASE}/api/credits`, {
    headers: { 'X-Lipaira-Key': key }
  })
  
  if (res.status === 401 || res.status === 403) {
    localStorage.clear()
    window.location = '/signup'
    throw { error: 'Unauthorized' }
  }
  
  const data = await res.json()
  return {
    credits: data.credits || data.balance || 0,
    created_at: new Date().toISOString(),
    last_active: data.last_used || null,
    user_id: data.user_id
  }
}

export async function sendMessage(message) {
  const key = getKey()
  const res = await fetch(`${BASE}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Lipaira-Key': key
    },
    body: JSON.stringify({ message })
  })
  
  const data = await res.json()
  
  if (res.status === 402) throw { error: 'Insufficient credits' }
  if (res.status === 401 || res.status === 403) {
    localStorage.clear()
    window.location = '/signup'
    throw { error: 'Unauthorized' }
  }
  
  if (!res.ok) throw { error: data.error || 'Request failed' }
  
  // Map to expected format
  return {
    reply: data.content || data.response || 'Done',
    credits_remaining: data.credits || 0,
    credits_used: 0
  }
}

export async function getConversationHistory() {
  const key = getKey()
  const res = await fetch(`${BASE}/api/conversation/history`, {
    headers: { 'X-Lipaira-Key': key }
  })
  
  if (!res.ok) return []
  
  const data = await res.json()
  // Convert to Chat.jsx format: {role: 'user'/'agent', content: '...'}
  return data.map(msg => ({
    role: msg.role === 'user' ? 'user' : 'agent',
    content: msg.content
  }))
}

// ============================================================================
// Billing & Agents API
// ============================================================================

export async function getBillingStatus() {
  const key = getKey()
  const res = await fetch(`${BASE}/api/billing/status`, {
    headers: { 'Authorization': `Bearer ${key}` }
  })
  if (!res.ok) throw new Error('Failed to get billing status')
  return res.json()
}

export async function getAgents() {
  const key = getKey()
  const res = await fetch(`${BASE}/api/agents`, {
    headers: { 'Authorization': `Bearer ${key}` }
  })
  if (!res.ok) throw new Error('Failed to get agents')
  return res.json()
}

export async function hireAgent(agentType) {
  const key = getKey()
  const res = await fetch(`${BASE}/api/agents/hire`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${key}`
    },
    body: JSON.stringify({ agent_type: agentType })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Failed to hire agent')
  return data
}

export async function fireAgent(agentType) {
  const key = getKey()
  const res = await fetch(`${BASE}/api/agents/fire`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${key}`
    },
    body: JSON.stringify({ agent_type: agentType })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Failed to fire agent')
  return data
}

export async function purchaseCredits(amount) {
  const key = getKey()
  const res = await fetch(`${BASE}/api/billing/purchase`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${key}`
    },
    body: JSON.stringify({ amount })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Failed to purchase credits')
  return data
}

export async function getAutoRefill() {
  const key = getKey()
  const res = await fetch(`${BASE}/api/billing/auto-refill`, {
    headers: { 'Authorization': `Bearer ${key}` }
  })
  if (!res.ok) throw new Error('Failed to get auto-refill settings')
  return res.json()
}

export async function setAutoRefill(settings) {
  const key = getKey()
  const res = await fetch(`${BASE}/api/billing/auto-refill`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${key}`
    },
    body: JSON.stringify(settings)
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Failed to set auto-refill')
  return data
}