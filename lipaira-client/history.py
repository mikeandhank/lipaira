"""
Conversation history stored in Postgres.
Each user has a conversation_history table row per session.
"""
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_history_table():
    """Create table if not exists. Call on agent startup."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
CREATE TABLE IF NOT EXISTS conversation_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conv_history_user_session
ON conversation_history(user_id, session_id);
""")
            conn.commit()

def get_history(user_id: str, session_id: str, max_messages: int = 20) -> list:
    """Retrieve recent conversation history for a user session."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
SELECT role, content
FROM conversation_history
WHERE user_id = %s AND session_id = %s
ORDER BY created_at DESC
LIMIT %s
""", (user_id, session_id, max_messages))
            rows = cur.fetchall()
            rows.reverse()
            return [{"role": row["role"], "content": row["content"]} for row in rows]

def save_message(user_id: str, session_id: str, role: str, content) -> None:
    """Save a single message to history."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
INSERT INTO conversation_history (user_id, session_id, role, content)
VALUES (%s, %s, %s, %s)
""", (
                user_id,
                session_id,
                role,
                json.dumps(content) if not isinstance(content, str) else json.dumps(content)
            ))
            conn.commit()

def clear_session(user_id: str, session_id: str) -> None:
    """Clear history for a specific session."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
DELETE FROM conversation_history
WHERE user_id = %s AND session_id = %s
""", (user_id, session_id))
            conn.commit()

def list_sessions(user_id: str) -> list:
    """List all session IDs for a user with last activity time."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
SELECT session_id, MAX(created_at) as last_active,
COUNT(*) as message_count
FROM conversation_history
WHERE user_id = %s
GROUP BY session_id
ORDER BY last_active DESC
""", (user_id,))
            return cur.fetchall()
