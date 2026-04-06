import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Landing from './pages/Landing'
import Signup from './pages/Signup'
import Login from './pages/Login'
import VerifyEmail from './pages/VerifyEmail'
import Onboarding from './pages/Onboarding'
import Integrations from './pages/Integrations'
import Dashboard from './pages/Dashboard'
import Chat from './pages/Chat'
import Sidebar from './components/Sidebar'
import './styles/theme.css'

function ProtectedRoute({ children }) {
  const key = localStorage.getItem('lipaira_api_key')
  if (!key) return <Navigate to="/signup" />
  return children
}

function ChatWithSidebar() {
  return (
    <div style={{display: 'flex'}}>
      <Sidebar />
      <div style={{flex: 1, marginLeft: '260px'}}>
        <Chat />
      </div>
    </div>
  )
}

function DashboardWithSidebar() {
  return (
    <div style={{display: 'flex'}}>
      <Sidebar />
      <div style={{flex: 1, marginLeft: '260px'}}>
        <Dashboard />
      </div>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/login" element={<Login />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route 
          path="/dashboard" 
          element={
            <ProtectedRoute>
              <DashboardWithSidebar />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/integrations" 
          element={
            <ProtectedRoute>
              <Integrations />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/chat" 
          element={
            <ProtectedRoute>
              <ChatWithSidebar />
            </ProtectedRoute>
          } 
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App
