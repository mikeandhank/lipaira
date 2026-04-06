// Landing.jsx - Public landing page

import { Link } from 'react-router-dom'

export default function Landing() {
  return (
    <div style={styles.container}>
      {/* Nav */}
      <nav style={styles.nav}>
        <div style={styles.navLeft}>Lipaira</div>
        <Link to="/login" style={styles.navRight}>Sign in</Link>
      </nav>

      {/* Hero */}
      <section style={styles.hero}>
        <h1 style={styles.headline}>Your AI agent. Secure by design.</h1>
        <p style={styles.subheadline}>
          A model-agnostic agent OS that keeps your data private, your keys safe, and your workflows yours.
        </p>
        <div style={styles.ctas}>
          <Link to="/signup" style={styles.primaryBtn}>Get started free</Link>
          <a href="#features" style={styles.secondaryLink}>See how it works ↓</a>
        </div>
      </section>

      {/* Features */}
      <section id="features" style={styles.features}>
        <div style={styles.featureCard}>
          <div style={styles.featureLabel}>Kernel-level isolation</div>
          <div style={styles.featureDesc}>
            Every agent runs in its own sandbox. A bad plugin can't touch your files or anyone else's.
          </div>
        </div>
        <div style={styles.featureCard}>
          <div style={styles.featureLabel}>Model-agnostic routing</div>
          <div style={styles.featureDesc}>
            Connect any LLM. We route to the best model for your price and quality preferences automatically.
          </div>
        </div>
        <div style={styles.featureCard}>
          <div style={styles.featureLabel}>Control from anywhere</div>
          <div style={styles.featureDesc}>
            Start a task from your phone, come back to the result on your desktop. Your agent runs 24/7.
          </div>
        </div>
      </section>

      {/* Comparison */}
      <section style={styles.comparison}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}></th>
              <th style={styles.th}>Lipaira</th>
              <th style={styles.th}>OpenClaw</th>
              <th style={styles.th}>Copilot Cowork</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={styles.td}>OS-level security</td>
              <td style={styles.tdYes}>✅</td>
              <td style={styles.tdNo}>❌</td>
              <td style={styles.tdYes}>✅</td>
            </tr>
            <tr>
              <td style={styles.td}>Self-hosted option</td>
              <td style={styles.tdYes}>✅</td>
              <td style={styles.tdYes}>✅</td>
              <td style={styles.tdNo}>❌</td>
            </tr>
            <tr>
              <td style={styles.td}>Model agnostic</td>
              <td style={styles.tdYes}>✅</td>
              <td style={styles.tdYes}>✅</td>
              <td style={styles.tdNo}>❌</td>
            </tr>
            <tr>
              <td style={styles.td}>No technical setup required</td>
              <td style={styles.tdYes}>✅</td>
              <td style={styles.tdNo}>❌</td>
              <td style={styles.tdYes}>✅</td>
            </tr>
            <tr>
              <td style={styles.td}>Works for SMBs</td>
              <td style={styles.tdYes}>✅</td>
              <td style={styles.tdNo}>❌</td>
              <td style={styles.tdNo}>❌</td>
            </tr>
          </tbody>
        </table>
      </section>

      {/* CTA Footer */}
      <section style={styles.cta}>
        <div style={styles.ctaTitle}>Ready to try it?</div>
        <Link to="/signup" style={styles.primaryBtn}>Create free account</Link>
      </section>
    </div>
  )
}

const styles = {
  container: {
    minHeight: '100vh',
    background: '#FAFAFA',
    color: '#111',
  },
  nav: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '20px 40px',
    maxWidth: '960px',
    margin: '0 auto',
  },
  navLeft: {
    fontSize: '20px',
    fontWeight: '500',
  },
  navRight: {
    color: '#555',
    textDecoration: 'none',
    fontSize: '14px',
  },
  hero: {
    textAlign: 'center',
    padding: '80px 20px',
    maxWidth: '700px',
    margin: '0 auto',
  },
  headline: {
    fontSize: '48px',
    fontWeight: '700',
    marginBottom: '16px',
    lineHeight: 1.1,
  },
  subheadline: {
    fontSize: '18px',
    color: '#555',
    marginBottom: '32px',
    lineHeight: 1.5,
  },
  ctas: {
    display: 'flex',
    gap: '24px',
    justifyContent: 'center',
    alignItems: 'center',
  },
  primaryBtn: {
    display: 'inline-block',
    padding: '14px 28px',
    background: 'linear-gradient(135deg, #6366f1, #a855f7)',
    border: 'none',
    borderRadius: '8px',
    color: 'white',
    fontSize: '16px',
    fontWeight: '600',
    textDecoration: 'none',
  },
  secondaryLink: {
    color: '#555',
    textDecoration: 'none',
    fontSize: '14px',
  },
  features: {
    display: 'flex',
    gap: '24px',
    maxWidth: '960px',
    margin: '0 auto',
    padding: '40px 20px',
    flexWrap: 'wrap',
    justifyContent: 'center',
  },
  featureCard: {
    flex: '1 1 280px',
    maxWidth: '300px',
    padding: '24px',
    background: 'white',
    borderRadius: '12px',
    border: '1px solid #eee',
  },
  featureLabel: {
    fontSize: '16px',
    fontWeight: '600',
    marginBottom: '8px',
  },
  featureDesc: {
    fontSize: '14px',
    color: '#555',
    lineHeight: 1.5,
  },
  comparison: {
    maxWidth: '800px',
    margin: '0 auto',
    padding: '40px 20px',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '14px',
  },
  th: {
    textAlign: 'left',
    padding: '12px',
    borderBottom: '1px solid #ddd',
    fontWeight: '600',
  },
  td: {
    padding: '12px',
    borderBottom: '1px solid #eee',
    color: '#555',
  },
  tdYes: {
    padding: '12px',
    borderBottom: '1px solid #eee',
    textAlign: 'center',
  },
  tdNo: {
    padding: '12px',
    borderBottom: '1px solid #eee',
    textAlign: 'center',
    opacity: 0.5,
  },
  cta: {
    textAlign: 'center',
    padding: '80px 20px',
  },
  ctaTitle: {
    fontSize: '24px',
    fontWeight: '600',
    marginBottom: '24px',
  },
}