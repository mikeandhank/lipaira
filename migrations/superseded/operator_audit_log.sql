-- operator_audit_log table for Lipaira
-- Logs every skill execution for security and compliance

CREATE TABLE IF NOT EXISTS operator_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    business_id UUID,
    skill_name VARCHAR(100) NOT NULL,
    params JSONB,
    result JSONB,
    approved_by VARCHAR(50) DEFAULT 'user',  -- 'user', 'auto', 'workflow'
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_user ON operator_audit_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_skill ON operator_audit_log(skill_name, created_at DESC);

-- pending_items table for follow-up tracking
CREATE TABLE IF NOT EXISTS pending_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    completed BOOLEAN DEFAULT FALSE,
    due_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pending_user ON pending_items(user_id, completed, due_date);

-- conversation_episodes for conversation summaries
CREATE TABLE IF NOT EXISTS conversation_episodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    summary TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_episodes_user ON conversation_episodes(user_id, created_at DESC);