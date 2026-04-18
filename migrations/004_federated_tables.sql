-- Migration 004: Federated Intelligence tables
-- Block 4 Item 18: Federated Intelligence foundation

CREATE TABLE IF NOT EXISTS user_profiles (
    id SERIAL PRIMARY KEY,
    user_id TEXT UNIQUE NOT NULL,
    business_type TEXT,
    location TEXT,
    employee_count INTEGER,
    annual_revenue DECIMAL(12,2),
    federated_opt_in BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_optin ON user_profiles(federated_opt_in);
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);
