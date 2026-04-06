-- Integration health tracking table
-- Created: 2026-04-01
-- Purpose: Monitor connected integrations for credential expiry and failures

CREATE TABLE IF NOT EXISTS integration_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    business_id UUID REFERENCES businesses(id),
    provider VARCHAR(50) NOT NULL,  -- quickbooks, google, godaddy, shopify, squarespace
    status VARCHAR(20) DEFAULT 'green',  -- green, yellow, red, gray
    last_checked TIMESTAMP DEFAULT NOW(),
    last_success TIMESTAMP,
    failure_count INTEGER DEFAULT 0,
    failure_reason TEXT,
    expires_at TIMESTAMP,  -- for OAuth tokens
    notified_at TIMESTAMP,  -- when we last told the user
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, provider, business_id)
);

CREATE INDEX IF NOT EXISTS idx_integration_health_user ON integration_health(user_id);
CREATE INDEX IF NOT EXISTS idx_integration_health_status ON integration_health(status);