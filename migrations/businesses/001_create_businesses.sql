-- businesses table migration
-- Created: 2026-04-01
-- Purpose: Multi-business support for Lipaira

-- Business entity (one user can have multiple)
CREATE TABLE IF NOT EXISTS businesses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(100),  -- "plumbing", "consulting", "retail", etc.
    is_primary BOOLEAN DEFAULT false,  -- first business is primary
    context JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_businesses_user ON businesses(user_id);

-- Add business_id to all relevant tables
-- Run these one at a time, verify after each

ALTER TABLE user_integrations
 ADD COLUMN IF NOT EXISTS business_id UUID REFERENCES businesses(id);

ALTER TABLE agent_subscriptions
 ADD COLUMN IF NOT EXISTS business_id UUID REFERENCES businesses(id);

ALTER TABLE memory_nodes
 ADD COLUMN IF NOT EXISTS business_id UUID REFERENCES businesses(id);

ALTER TABLE conversation_messages
 ADD COLUMN IF NOT EXISTS business_id UUID REFERENCES businesses(id);

ALTER TABLE invoice_chase_log
 ADD COLUMN IF NOT EXISTS business_id UUID REFERENCES businesses(id);

ALTER TABLE credit_ledger
 ADD COLUMN IF NOT EXISTS business_id UUID REFERENCES businesses(id);