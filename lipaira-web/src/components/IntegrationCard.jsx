import React from 'react';

// Status color mapping
const STATUS_COLORS = {
  green: '#16a34a',
  yellow: '#d97706', 
  red: '#dc2626',
  gray: '#9ca3af'
};

export default function IntegrationCard({ 
  provider, 
  label, 
  status = 'gray', 
  detail,
  connected = false,
  onConnect, 
  onManage, 
  onDisconnect,
  onTest
}) {
  const statusColor = STATUS_COLORS[status] || STATUS_COLORS.gray;
  
  return (
    <div style={styles.card}>
      <div style={styles.left}>
        <span 
          style={{...styles.statusDot, background: statusColor}}
          title={status === 'green' ? 'Connected' : status === 'yellow' ? 'Expiring soon' : status === 'red' ? 'Needs reconnection' : 'Not connected'}
        />
        <div style={styles.info}>
          <span style={styles.label}>{label}</span>
          {detail && <span style={styles.detail}>{detail}</span>}
          {status === 'red' && (
            <span style={styles.warning}>Needs attention</span>
          )}
        </div>
      </div>
      <div style={styles.actions}>
        {connected ? (
          <>
            {onTest && (
              <button style={styles.btnSecondary} onClick={onTest}>
                Test
              </button>
            )}
            {onManage && (
              <button style={styles.btnSecondary} onClick={onManage}>
                Manage
              </button>
            )}
            {onDisconnect && (
              <button style={styles.btnDanger} onClick={onDisconnect}>
                Disconnect
              </button>
            )}
          </>
        ) : (
          <button style={styles.btnPrimary} onClick={onConnect}>
            Connect
          </button>
        )}
      </div>
    </div>
  );
}

// Integration Card for connecting new providers
export function IntegrationConnectCard({ 
  provider, 
  label, 
  description,
  icon,
  onConnect 
}) {
  return (
    <div style={styles.connectCard}>
      <div style={styles.connectLeft}>
        {icon && <span style={styles.icon}>{icon}</span>}
        <div style={styles.connectInfo}>
          <span style={styles.connectLabel}>{label}</span>
          {description && <span style={styles.connectDesc}>{description}</span>}
        </div>
      </div>
      <button style={styles.btnPrimary} onClick={onConnect}>
        Connect
      </button>
    </div>
  );
}

// Integration Modal for manage/connect flows
export function IntegrationModal({ 
  isOpen, 
  onClose, 
  provider, 
  integration,
  onTest,
  onDisconnect,
  onSave 
}) {
  if (!isOpen || !provider) return null;
  
  const isConnected = integration?.status !== 'gray' && integration?.status !== undefined;
  
  return (
    <div style={styles.modalOverlay} onClick={onClose}>
      <div style={styles.modal} onClick={e => e.stopPropagation()}>
        <div style={styles.modalHeader}>
          <h3 style={styles.modalTitle}>{provider.name}</h3>
          <button style={styles.closeBtn} onClick={onClose}>×</button>
        </div>
        
        <div style={styles.modalBody}>
          {isConnected ? (
            <>
              <div style={styles.modalSection}>
                <label style={styles.modalLabel}>Status</label>
                <div style={styles.statusRow}>
                  <span 
                    style={{
                      ...styles.statusBadge,
                      background: STATUS_COLORS[integration.status] || STATUS_COLORS.gray
                    }}
                  >
                    {integration.status}
                  </span>
                  {integration.expiresAt && (
                    <span style={styles.expiresAt}>
                      Expires: {new Date(integration.expiresAt).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>
              
              {integration.detail && (
                <div style={styles.modalSection}>
                  <label style={styles.modalLabel}>Connected Account</label>
                  <p style={styles.modalValue}>{integration.detail}</p>
                </div>
              )}
              
              {integration.lastSuccess && (
                <div style={styles.modalSection}>
                  <label style={styles.modalLabel}>Last Used</label>
                  <p style={styles.modalValue}>
                    {new Date(integration.lastSuccess).toLocaleString()}
                  </p>
                </div>
              )}
              
              {integration.failureReason && (
                <div style={styles.modalError}>
                  <strong>Error:</strong> {integration.failureReason}
                </div>
              )}
              
              <div style={styles.modalActions}>
                {onTest && (
                  <button style={styles.btnSecondary} onClick={() => onTest(provider.id)}>
                    Test Connection
                  </button>
                )}
                {onDisconnect && (
                  <button style={styles.btnDanger} onClick={() => onDisconnect(provider.id)}>
                    Disconnect
                  </button>
                )}
              </div>
            </>
          ) : (
            <>
              <p style={styles.modalDesc}>{provider.description}</p>
              <p style={styles.modalRequired}>
                Required: {provider.required.join(', ')}
              </p>
              {/* Provider-specific inputs would go here */}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const styles = {
  card: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 16px',
    background: '#fff',
    borderRadius: '8px',
    border: '1px solid #e5e7eb',
    marginBottom: '8px'
  },
  left: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px'
  },
  statusDot: {
    width: '10px',
    height: '10px',
    borderRadius: '50%',
    flexShrink: 0
  },
  info: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px'
  },
  label: {
    fontSize: '14px',
    fontWeight: '500',
    color: '#111'
  },
  detail: {
    fontSize: '12px',
    color: '#666'
  },
  warning: {
    fontSize: '12px',
    color: '#dc2626',
    fontWeight: '500'
  },
  actions: {
    display: 'flex',
    gap: '8px'
  },
  btnPrimary: {
    padding: '6px 12px',
    fontSize: '13px',
    fontWeight: '500',
    background: '#2563eb',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer'
  },
  btnSecondary: {
    padding: '6px 12px',
    fontSize: '13px',
    fontWeight: '500',
    background: '#f3f4f6',
    color: '#374151',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    cursor: 'pointer'
  },
  btnDanger: {
    padding: '6px 12px',
    fontSize: '13px',
    fontWeight: '500',
    background: '#fee2e2',
    color: '#dc2626',
    border: '1px solid #fecaca',
    borderRadius: '6px',
    cursor: 'pointer'
  },
  // Connect card styles
  connectCard: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 16px',
    background: '#f9fafb',
    borderRadius: '8px',
    border: '1px dashed #d1d5db',
    marginBottom: '8px'
  },
  connectLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px'
  },
  icon: {
    fontSize: '20px'
  },
  connectInfo: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px'
  },
  connectLabel: {
    fontSize: '14px',
    fontWeight: '500',
    color: '#374151'
  },
  connectDesc: {
    fontSize: '12px',
    color: '#6b7280'
  },
  // Modal styles
  modalOverlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: 'rgba(0,0,0,0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000
  },
  modal: {
    background: '#fff',
    borderRadius: '12px',
    width: '400px',
    maxWidth: '90%',
    boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)'
  },
  modalHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 20px',
    borderBottom: '1px solid #e5e7eb'
  },
  modalTitle: {
    margin: 0,
    fontSize: '18px',
    fontWeight: '600'
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    fontSize: '24px',
    cursor: 'pointer',
    color: '#6b7280',
    padding: 0,
    lineHeight: 1
  },
  modalBody: {
    padding: '20px'
  },
  modalSection: {
    marginBottom: '16px'
  },
  modalLabel: {
    display: 'block',
    fontSize: '12px',
    fontWeight: '600',
    color: '#6b7280',
    textTransform: 'uppercase',
    marginBottom: '4px'
  },
  modalValue: {
    margin: 0,
    fontSize: '14px',
    color: '#111'
  },
  statusRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px'
  },
  statusBadge: {
    padding: '2px 8px',
    borderRadius: '4px',
    fontSize: '12px',
    fontWeight: '500',
    color: '#fff',
    textTransform: 'capitalize'
  },
  expiresAt: {
    fontSize: '12px',
    color: '#6b7280'
  },
  modalError: {
    padding: '12px',
    background: '#fee2e2',
    borderRadius: '6px',
    fontSize: '13px',
    color: '#991b1b',
    marginBottom: '16px'
  },
  modalDesc: {
    margin: '0 0 8px',
    fontSize: '14px',
    color: '#374151'
  },
  modalRequired: {
    margin: 0,
    fontSize: '12px',
    color: '#6b7280'
  },
  modalActions: {
    display: 'flex',
    gap: '8px',
    marginTop: '20px'
  }
};