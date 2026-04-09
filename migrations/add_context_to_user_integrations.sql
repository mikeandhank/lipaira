-- Migration: Add context column to user_integrations
-- Run: psql -h postgres -U nexusos -d nexusos -f add_context_to_user_integrations.sql
-- Safe to run multiple times (IF NOT EXISTS)

ALTER TABLE user_integrations 
ADD COLUMN IF NOT EXISTS context JSONB DEFAULT NULL;