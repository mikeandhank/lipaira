-- Migration: Create operator_audit_log table
-- Run: psql -h postgres -U nexusos -d nexusos -f create_operator_audit_log.sql
-- Safe to run multiple times (IF NOT EXISTS)

CREATE TABLE IF NOT EXISTS operator_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    business_id UUID,
    action VARCHAR(100),
    skill_name VARCHAR(100),
    params JSONB,
    result JSONB,
    success BOOLEAN DEFAULT true,
    error TEXT,
    approved_by VARCHAR(50) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_user 
ON operator_audit_log(user_id, created_at DESC);