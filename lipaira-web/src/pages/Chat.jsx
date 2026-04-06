// Chat.jsx - Agent chat with markdown support

import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import { getMe, sendMessage } from '../api'

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [credits, setCredits] = useState(null)
  const [loading, setLoading] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(true)
  const [input, setInput] = useState('')
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const messagesEndRef = useRef(null)

  // Handle OAuth callback params
  useEffect(() => {
    // Small delay to ensure component is mounted
    setTimeout(() => {
      const params = new URLSearchParams(window.location.search)
      const connected = params.get('connected')
      const error = params.get('error')
      
      console.log('OAuth callback:', connected, error)
      
      if (connected) {
        setToast(`✅ ${connected} connected successfully!`)
        window.history.replaceState({}, '', '/chat')
        // Auto-hide after 5 seconds
        setTimeout(() => setToast(''), 5000)
      } else if (error) {
        setToast(`❌ ${error.replace(/_/g, ' ')}`)
        window.history.replaceState({}, '', '/chat')
        setTimeout(() => setToast(''), 5000)
      }
    }, 100)
  }, [])

  // Get initial credits and conversation history
  useEffect(() => {
    getMe().then(data => setCredits(data.credits))
    
    // Load conversation history directly with fetch
    const key = localStorage.getItem('lipaira_api_key')
    if (key) {
      fetch('/api/conversation/history', {
        headers: { 'X-Lipaira-Key': key }
      })
      .then(r => r.json())
      .then(data => {
        if (Array.isArray(data) && data.length > 0) {
          setMessages(data.map(m => ({
            role: m.role === 'user' ? 'user' : 'agent',
            content: m.content
          })))
        }
      })
      .catch(() => {})
      .finally(() => setHistoryLoading(false))
    } else {
      setHistoryLoading(false)
    }
  }, [])

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (input.trim() && !loading) {
        handleSend(e)
      }
    }
  }

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMsg = input
    setInput('')
    setLoading(true)
    setError('')

    // Add user message immediately
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])

    try {
      const data = await sendMessage(userMsg)
      
      // Add agent response
      setMessages(prev => [...prev, { 
        role: 'agent', 
        content: data.reply || 'Done' 
      }])
      
      // Update credits and notify sidebar
      if (data.credits_remaining !== undefined) {
        setCredits(data.credits_remaining)
        // Emit event for Sidebar to update
        window.dispatchEvent(new CustomEvent('creditsUpdated', {
          detail: data.credits_remaining
        }))
      }
      
    } catch (err) {
      if (err.error === 'Insufficient credits') {
        setError('402: Out of credits')
        setMessages(prev => [...prev, { 
          role: 'agent', 
          content: 'Error: Out of credits' 
        }])
      } else {
        setError(err.error || 'Request failed')
      }
    } finally {
      setLoading(false)
    }
  }

  const getCreditColor = (val) => {
    if (val > 20) return '#22c55e' // green
    if (val >= 5) return '#f59e0b' // amber
    return '#ef4444' // red
  }

  const formatCredits = (val) => {
    return val ? val.toFixed(2) : '0.00'
  }

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
      <div style={styles.header}>
        <div style={styles.logo}>Lipaira</div>
        <div style={{...styles.credits, color: getCreditColor(credits)}}>
          Credits: {formatCredits(credits)}
        </div>
      </div>

      <div style={styles.chatArea}>
        <div style={styles.messages}>
          {historyLoading && (
            <div style={styles.empty}>
              Loading conversation...
            </div>
          )}
          
          {!historyLoading && messages.length === 0 && (
            <div style={styles.empty}>
              Start a conversation with your agent
            </div>
          )}
          
          {messages.map((msg, i) => (
            <div 
              key={i} 
              style={{
                ...styles.message,
                ...(msg.role === 'user' ? styles.userMsg : styles.agentMsg)
              }}
            >
              {msg.role === 'user' ? (
                msg.content
              ) : (
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              )}
            </div>
          ))}

          {loading && (
            <div style={{...styles.message, ...styles.agentMsg}}>
              <span style={styles.typingIndicator}>
                <span style={styles.typingDot}></span>
                <span style={styles.typingDot}></span>
                <span style={styles.typingDot}></span>
              </span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {error && error.includes('402') && (
          <div style={styles.errorBanner}>Insufficient credits</div>
        )}

        <form onSubmit={handleSend} style={styles.inputArea}>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message your agent..."
            style={styles.input}
            rows={1}
            disabled={loading}
          />
          <button 
            type="submit" 
            style={styles.sendBtn}
            disabled={loading || !input.trim()}
          >
            Send
          </button>
        </form>
      </div>
    </div>
  )
}

const styles = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column',
    background: 'var(--bg-primary)',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 24px',
    borderBottom: '1px solid var(--border-color)',
    background: 'var(--bg-secondary)',
  },
  logo: {
    fontSize: '20px',
    fontWeight: '700',
    background: 'var(--brand-gradient)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  },
  credits: {
    fontSize: '14px',
    fontWeight: '600',
    padding: '8px 16px',
    background: 'var(--bg-tertiary)',
    borderRadius: '20px',
    color: 'var(--text-primary)',
  },
  chatArea: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    maxWidth: '800px',
    margin: '0 auto',
    width: '100%',
  },
  messages: {
    flex: 1,
    overflowY: 'auto',
    padding: '20px',
  },
  message: {
    maxWidth: '80%',
    padding: '10px 14px',
    borderRadius: '16px',
    marginBottom: '8px',
    whiteSpace: 'pre-wrap',
    fontSize: '14px',
    lineHeight: 1.5,
  },
  userMsg: {
    marginLeft: 'auto',
    background: 'var(--brand-gradient)',
    color: 'var(--text-inverse)',
    borderBottomRightRadius: '4px',
  },
  agentMsg: {
    background: 'var(--bg-tertiary)',
    color: 'var(--text-primary)',
    borderBottomLeftRadius: '4px',
  },
  empty: {
    textAlign: 'center',
    color: 'var(--text-secondary)',
    marginTop: '100px',
  },
  typingIndicator: {
    display: 'inline-flex',
    gap: '4px',
  },
  typingDot: {
    display: 'inline-block',
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    background: '#888',
    animation: 'typing-bounce 1.2s infinite ease-in-out',
  },
  inputArea: {
    display: 'flex',
    gap: '10px',
    padding: '16px 20px',
    borderTop: '1px solid var(--border-color)',
  },
  input: {
    flex: 1,
    padding: '14px 16px',
    background: 'var(--input-bg)',
    border: '1px solid var(--input-border)',
    borderRadius: 'var(--border-radius)',
    color: 'var(--text-primary)',
    fontSize: '16px',
    resize: 'none',
    fontFamily: 'inherit',
  },
  sendBtn: {
    padding: '14px 24px',
    background: 'var(--brand-gradient)',
    border: 'none',
    borderRadius: 'var(--border-radius)',
    color: 'var(--text-inverse)',
    fontWeight: '600',
  },
  errorBanner: {
    padding: '12px',
    background: 'var(--color-danger)',
    color: 'var(--text-inverse)',
    textAlign: 'center',
    fontSize: '14px',
  },
}