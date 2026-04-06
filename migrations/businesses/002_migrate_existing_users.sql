-- Migrate existing users: create primary business for each
-- Run after 001_create_businesses.sql

-- Insert primary business for each existing user
INSERT INTO businesses (user_id, name, is_primary)
SELECT
    u.id,
    COALESCE(
        up.context->>'business_name',
        COALESCE(u.name, 'My Business') || '''s Business'
    ),
    true
FROM users u
LEFT JOIN user_profiles up ON up.user_id = u.id
ON CONFLICT DO NOTHING;

-- Link existing integrations to primary business
UPDATE user_integrations ui
SET business_id = b.id
FROM businesses b
WHERE b.user_id = ui.user_id
AND b.is_primary = true
AND ui.business_id IS NULL;

-- Link existing conversations to primary business
UPDATE conversation_messages cm
SET business_id = b.id
FROM businesses b
WHERE b.user_id = cm.user_id
AND b.is_primary = true
AND cm.business_id IS NULL
RETURNING count(*);