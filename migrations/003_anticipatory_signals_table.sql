-- 003_anticipatory_signals_table.sql
-- Anticipatory Scheduler signals table
-- Block 4 Item 17

BEGIN;

CREATE TABLE IF NOT EXISTS anticipatory_signals (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    urgency TEXT NOT NULL CHECK (urgency IN ('high', 'medium', 'low')),
    title TEXT NOT NULL,
    description TEXT,
    action_suggested TEXT,
    metadata JSONB DEFAULT '{}',
    status VARCHAR(32) DEFAULT 'pending',
    surfaced BOOLEAN DEFAULT FALSE,
    surfaced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signals_user ON anticipatory_signals(user_id);
CREATE INDEX IF NOT EXISTS idx_signals_surfaced ON anticipatory_signals(surfaced);
CREATE INDEX IF NOT EXISTS idx_signals_status ON anticipatory_signals(status);

-- billing_history table (referenced by anticipatory_scheduler)
CREATE TABLE IF NOT EXISTS billing_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    amount_cents INTEGER NOT NULL,
    description TEXT,
    invoice_date TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_billing_history_user ON billing_history(user_id);

COMMIT;
