"""
Audit Logger — compliance and debugging log for operator actions.
Records every platform operation (intent, action, platform, before/after state,
status) to the audit_log table. Includes compute_intent_hash() for deduplication
and get_audit_logger() singleton pattern. All operator actions are logged.
"""
import os
import json
import logging
import uuid
import hashlib
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """An audit log entry."""
    id: str
    user_id: str
    intent_hash: str
    command: str
    action: str
    platform: str
    before_state: Optional[Dict] = None
    after_state: Optional[Dict] = None
    status: str = "pending"  # pending, success, failed
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


class AuditLogger:
    """
    Logs operator actions to database for compliance.
    """
    
    def __init__(self):
        self._ensure_table()
    
    def _ensure_table(self):
        """Create audit table if not exists."""
        import psycopg2
        from urllib.parse import urlparse
        
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            logger.warning("DATABASE_URL not set, audit logging disabled")
            return
        
        result = urlparse(db_url)
        
        try:
            conn = psycopg2.connect(
                host=result.hostname,
                port=result.port or 5432,
                database=result.path.lstrip("/"),
                user=result.username,
                password=result.password
            )
            
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS operator_audit (
                        id UUID PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        intent_hash VARCHAR(64) NOT NULL,
                        command TEXT,
                        action VARCHAR(50) NOT NULL,
                        platform VARCHAR(50) NOT NULL,
                        before_state JSONB,
                        after_state JSONB,
                        status VARCHAR(20) DEFAULT 'pending',
                        error TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                conn.commit()
            
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to create audit table: {e}")
    
    def _get_connection(self):
        """Get database connection."""
        import psycopg2
        from urllib.parse import urlparse
        
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            return None
        
        result = urlparse(db_url)
        return psycopg2.connect(
            host=result.hostname,
            port=result.port or 5432,
            database=result.path.lstrip("/"),
            user=result.username,
            password=result.password
        )
    
    def log_action(self, user_id: str, intent_hash: str, command: str,
                   action: str, platform: str,
                   before_state: Dict = None, after_state: Dict = None,
                   status: str = "success", error: str = None) -> str:
        """Log a single action."""
        entry_id = str(uuid.uuid4())
        
        conn = self._get_connection()
        if not conn:
            return entry_id
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO operator_audit 
                    (id, user_id, intent_hash, command, action, platform, 
                     before_state, after_state, status, error)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    entry_id,
                    user_id,
                    intent_hash,
                    command,
                    action,
                    platform,
                    json.dumps(before_state) if before_state else None,
                    json.dumps(after_state) if after_state else None,
                    status,
                    error
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log audit: {e}")
        finally:
            conn.close()
        
        return entry_id
    
    def get_history(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get audit history for a user."""
        conn = self._get_connection()
        if not conn:
            return []
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, intent_hash, command, action, platform, 
                           status, error, created_at
                    FROM operator_audit
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (user_id, limit))
                
                return [
                    {
                        "id": row[0],
                        "intent_hash": row[1],
                        "command": row[2],
                        "action": row[3],
                        "platform": row[4],
                        "status": row[5],
                        "error": row[6],
                        "created_at": row[7].isoformat() if row[7] else None
                    }
                    for row in cur.fetchall()
                ]
        except Exception as e:
            logger.error(f"Failed to get audit history: {e}")
            return []
        finally:
            conn.close()


def compute_intent_hash(command: str, intent_data: Dict) -> str:
    """Compute a hash of the intent for deduplication."""
    data = f"{command}:{json.dumps(intent_data, sort_keys=True)}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]


# Global instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger