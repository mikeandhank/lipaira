"""
Audit logging for skill executions and security-critical actions.
Every consequential action gets logged for security and compliance.

Two tiers:
- Critical (require_audit): login, key issuance, permission changes.
  Fails the operation if DB audit write fails. Raises AuditLogError.
- Non-critical (log_audit): skill executions, general API calls.
  Falls back to file + stderr on failure. Never blocks execution.

Note: Fallback logs to /var/log/lipaira/audit_fallback.jsonl.
These logs are ephemeral — they exist only inside the container and are
lost on container restart unless /var/log/lipaira is mounted as a volume.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from functools import wraps
from typing import Optional

logger = logging.getLogger(__name__)


class AuditLogError(Exception):
    """Raised when a critical audit log write fails and the operation must be rejected."""
    pass


def _write_fallback_log(entry: dict, fallback_path: str = "/var/log/lipaira/audit_fallback.jsonl"):
    """
    Write audit entry to fallback file when DB is unavailable.
    
    Note: These logs are ephemeral — stored inside the container.
    They are lost on container restart unless /var/log/lipaira is
    mounted as a persistent volume from the host.
    """
    try:
        os.makedirs(os.path.dirname(fallback_path), exist_ok=True)
        with open(fallback_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # Last resort: at least we tried the file


def _audit_log_entry(user_id: str, action: str, params: Optional[dict] = None,
                     success: bool = True, error: Optional[str] = None) -> dict:
    """Build a standard audit log entry."""
    return {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "action": action,
        "params": params or {},
        "success": success,
        "error": error,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def log_audit(user_id: str, action: str, params: Optional[dict] = None,
              success: bool = True, error: Optional[str] = None):
    """
    Non-critical audit log — continues on failure with fallback.
    
    Use for: skill executions, general API calls, read operations.
    If DB write fails, writes to /var/log/lipaira/audit_fallback.jsonl
    and logs to stderr. Does not block the calling code.
    """
    entry = _audit_log_entry(user_id, action, params, success, error)
    
    try:
        import psycopg2
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            raise RuntimeError("DATABASE_URL environment variable is required")
        
        conn = psycopg2.connect(db_url)
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO operator_audit_log 
                (user_id, action, params, success, error, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, action, json.dumps(params or {}),
                  success, error, datetime.utcnow()))
            conn.commit()
        conn.close()
        logger.info(f"Audit log: [{action}] {user_id} success={success}")
        
    except Exception as e:
        # Fallback: write to file + stderr. Never block.
        logger.warning(
            f"AUDIT FALLBACK: user_id={user_id} action={action} "
            f"timestamp={entry['timestamp']} error={str(e)}"
        )
        _write_fallback_log(entry)


def require_audit(action: str):
    """
    Decorator for critical security paths — rejects on audit failure.
    
    Use on: login, register, logout, key issuance, permission changes.
    If DB write fails, raises AuditLogError — the calling endpoint
    must catch this and return 500.
    
    Usage:
        @app.route('/api/auth/login', methods=['POST'])
        @require_audit("login")
        def login():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Extract user_id from Flask g object if available
            user_id = None
            try:
                from flask import g
                user_id = getattr(g, 'user_id', None)
            except ImportError:
                pass
            
            success = True
            error = None
            result = None
            
            try:
                result = f(*args, **kwargs)
                return result
            except AuditLogError:
                raise  # Already handled
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                if user_id:
                    entry = _audit_log_entry(user_id, action, {"endpoint": f.__name__}, success, error)
                    try:
                        import psycopg2
                        db_url = os.environ.get('DATABASE_URL')
                        if not db_url:
                            raise RuntimeError("DATABASE_URL required")
                        
                        conn = psycopg2.connect(db_url)
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO operator_audit_log 
                                (user_id, action, params, success, error, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (user_id, action, json.dumps({"endpoint": f.__name__}),
                                  success, error, datetime.utcnow()))
                            conn.commit()
                        conn.close()
                    except Exception as db_e:
                        # Critical path — DB write MUST succeed or we reject
                        logger.error(
                            f"AUDIT CRITICAL FAILURE: user_id={user_id} action={action} "
                            f"db_error={str(db_e)} — operation rejected"
                        )
                        raise AuditLogError(
                            f"Critical audit write failed for action={action}, user_id={user_id}. "
                            f"Operation rejected. DB error: {db_e}"
                        )
        
        return decorated
    return decorator


# Alias for backward compatibility
def log_skill_execution(user_id: str, skill_name: str,
                        params: dict, result: dict,
                        approved_by: str = "user"):
    """Legacy alias — maps to log_audit with skill_name as action."""
    log_audit(
        user_id=user_id,
        action=f"skill:{skill_name}",
        params={"params": params, "result": result, "approved_by": approved_by},
        success=True,
    )


def create_audit_log_table():
    """Create the audit log table if it doesn't exist."""
    import psycopg2
    
    try:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            raise RuntimeError("DATABASE_URL environment variable is required")
        conn = psycopg2.connect(db_url)
        
        with conn.cursor() as cur:
            # Check if action column exists (schema migration)
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'operator_audit_log' AND column_name = 'action'
            """)
            has_action = cur.fetchone() is not None
            
            if has_action:
                # New schema — action + success + error
                cur.execute("""
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
                """)
            else:
                # Original schema — skill_name based
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS operator_audit_log (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id VARCHAR(255) NOT NULL,
                        business_id UUID,
                        skill_name VARCHAR(100) NOT NULL,
                        params JSONB,
                        result JSONB,
                        approved_by VARCHAR(50) DEFAULT 'user',
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                """)
            
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_user 
                ON operator_audit_log(user_id, created_at DESC)
            """)
            conn.commit()
        
        conn.close()
        logger.info("Audit log table ready")
    except Exception as e:
        logger.warning(f"Failed to create audit log table: {e}")
