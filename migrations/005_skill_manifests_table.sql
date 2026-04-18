-- Migration: 005_skill_manifests_table.sql
-- Creates skill_manifests table for storing skill metadata

CREATE TABLE IF NOT EXISTS skill_manifests (
    id SERIAL PRIMARY KEY,
    skill_name TEXT UNIQUE NOT NULL,
    version TEXT NOT NULL,
    description TEXT,
    author TEXT,
    source TEXT DEFAULT 'local',  -- 'local', 'marketplace'
    file_path TEXT,
    dependencies TEXT[],  -- Array of dependency names
    installed_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(skill_name, version)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_skill_manifests_name ON skill_manifests(skill_name);
CREATE INDEX IF NOT EXISTS idx_skill_manifests_source ON skill_manifests(source);

-- Comments
COMMENT ON TABLE skill_manifests IS 'Stores metadata for installed skills';
COMMENT ON COLUMN skill_manifests.skill_name IS 'Unique skill identifier';
COMMENT ON COLUMN skill_manifests.version IS 'Semantic version string';
COMMENT ON COLUMN skill_manifests.source IS 'Installation source: local, marketplace';
COMMENT ON COLUMN skill_manifests.file_path IS 'Absolute path to skill file';
COMMENT ON COLUMN skill_manifests.dependencies IS 'List of required skill/module dependencies';
