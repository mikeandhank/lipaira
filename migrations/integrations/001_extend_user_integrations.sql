-- Migration: Extend user_integrations for DNS/Website integrations
-- Run: psql -h postgres -U nexusos -d nexusos -f 001_extend_user_integrations.sql

-- Add new columns to existing user_integrations table
ALTER TABLE user_integrations 
ADD COLUMN IF NOT EXISTS provider_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS domain VARCHAR(255),
ADD COLUMN IF NOT EXISTS site_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS rate_limit INTEGER DEFAULT 60,
ADD COLUMN IF NOT EXISTS last_api_call TIMESTAMP;

-- DNS records managed by Lipaira
CREATE TABLE IF NOT EXISTS dns_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    record_type VARCHAR(10) NOT NULL,
    name VARCHAR(255) NOT NULL,
    value TEXT NOT NULL,
    ttl INTEGER DEFAULT 3600,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, provider, record_type, name)
);

-- Sync log for auditing integration operations
CREATE TABLE IF NOT EXISTS integration_sync_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Products/services synced from external platforms
CREATE TABLE IF NOT EXISTS integration_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    external_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    price_cents INTEGER,
    description TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, provider, external_id)
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_dns_records_user_provider 
ON dns_records(user_id, provider);

CREATE INDEX IF NOT EXISTS idx_integration_sync_log_user 
ON integration_sync_log(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_integration_products_user 
ON integration_products(user_id, provider);

-- Comments for documentation
COMMENT ON COLUMN user_integrations.provider_type IS 'Type: registrar, website, ecommerce, email';
COMMENT ON COLUMN user_integrations.domain IS 'Primary domain being managed (e.g., davesplumbing.com)';
COMMENT ON COLUMN user_integrations.site_id IS 'Provider internal site ID';
COMMENT ON COLUMN user_integrations.rate_limit IS 'API rate limit per minute';
COMMENT ON COLUMN user_integrations.last_api_call IS 'Last API call timestamp for rate limiting';