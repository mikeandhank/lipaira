import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'

// Error boundary to catch render errors
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  componentDidCatch(error, errorInfo) {
    console.error('React Error:', error, errorInfo)
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{padding: '20px', background: '#1a1a2e', color: '#fff', minHeight: '100vh'}}>
          <h1>Something went wrong</h1>
          <pre>{this.state.error?.toString()}</pre>
        </div>
      )
    }
    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
)
