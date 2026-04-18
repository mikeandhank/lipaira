-- 002_events_table.sql
-- Block 4 Item 16: Event Queue persistent storage

CREATE TABLE IF NOT EXISTS events (
  id SERIAL PRIMARY KEY,
  event_type TEXT NOT NULL,
  payload JSONB,
  user_id TEXT,
  status TEXT DEFAULT 'pending',
  failure_count INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
