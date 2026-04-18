"""
Fail-Safe Audit Logging for Lipaira.

Implements Contract C2: Fail-Safe Audit Logging
https://github.com/mikeandhank/lipaira-specs/blob/main/COMPLIANCE_FIXES_CONTRACTS.md

Architecture:
    audit_event → [primary: DB write, retry 3x with exponential backoff]
                 → [fallback: /var/log/lipaira/audit/YYYY-MM-DD.jsonl]
                 → [if both fail: logger.error → triggers alerting]

File path: /var/log/lipaira/audit/audit.log (mounted from host)
File format: newline-delimited JSON ({"ts", "user_id", "action", "payload_hash", "status"})
File rotation: daily, retain 90 days (configurable)
DB write: retry 3x with exponential backoff before falling to file
"""

import hashlib
import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Constants for Contract C2 compliance
AUDIT_FALLBACK_DIR = "/var/log/lipaira/audit"
AUDIT_FALLBACK_FILE = "audit.log"  # Daily rotation appends YYYY-MM-DD prefix
AUDIT_RETENTION_DAYS = 90
MAX_DB_RETRIES = 3
DB_RETRY_BASE_DELAY = 0.5  # seconds, exponential backoff


class AuditLogError(Exception):
    """Raised when a critical audit log write fails and the operation must be rejected."""
    pass


def _hash_payload(params: Optional[dict]) -> str:
    """Create a SHA256 hash of the payload for audit trail integrity."""
    if params is None:
        return ""
    try:
        payload_str = json.dumps(params, sort_keys=True, default=str)
        return hashlib.sha256(payload_str.encode()).hexdigest()[:16]
    except Exception:
        return "hash-error"


def _get_fallback_path() -> str:
    """Get the daily rotating fallback log path."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    fallback_dir = Path(AUDIT_FALLBACK_DIR)
    return str(fallback_dir / f"{today}-{AUDIT_FALLBACK_FILE}")


def _write_fallback_log(entry: dict, fallback_path: str = None) -> bool:
    """
    Write audit entry to append-only fallback file when DB is unavailable.
    
    Returns True if write succeeded, False if it also failed.
    """
    if fallback_path is None:
        fallback_path = _get_fallback_path()
    
    try:
        Path(fallback_path).parent.mkdir(parents=True, exist_ok=True)
        with open(fallback_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        return True
    except Exception as e:
        # Last resort: log critical error
        logger.error(
            f"AUDIT BOTH FAILURES: user_id={entry.get('user_id')} action={entry.get('action')} "
            f"timestamp={entry.get('ts')} — file_write_error={str(e)}"
        )
        return False


def _audit_log_entry(user_id: str, action: str, params: Optional[dict] = None,
                     success: bool = True, error: Optional[str] = None) -> dict:
    """Build a standard audit log entry in Contract C2 format."""
    return {
        "ts": datetime.utcnow().isoformat() + "Z",
        "user_id": user_id,
        "action": action,
        "payload_hash": _hash_payload(params),
        "status": "success" if success else "failed",
        "error": error,
    }


def _db_write_with_retry(user_id: str, action: str, params: Optional[dict] = None,
                          success: bool = True, error: Optional[str] = None) -> bool:
    """
    Write audit entry to database with exponential backoff retry.
    
    Returns True if DB write succeeded, False if all retries exhausted.
    """
    entry = _audit_log_entry(user_id, action, params, success, error)
    
    for attempt in range(1, MAX_DB_RETRIES + 1):
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
            return True
            
        except Exception as e:
            if attempt == MAX_DB_RETRIES:
                logger.warning(
                    f"AUDIT DB FAILURE (all retries exhausted): user_id={user_id} action={action} "
                    f"timestamp={entry['ts']} error={str(e)}"
                )
                return False
            else:
                delay = DB_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    f"AUDIT DB RETRY {attempt}/{MAX_DB_RETRIES}: user_id={user_id} action={action} "
                    f"delay={delay}s error={str(e)}"
                )
                time.sleep(delay)
    
    return False


def log_audit(user_id: str, action: str, params: Optional[dict] = None,
              success: bool = True, error: Optional[str] = None):
    """
    Non-critical audit log — continues on failure with fallback.
    
    Contract C2 implementation:
    1. Try DB write with retry 3x exponential backoff
    2. On DB failure, fall back to /var/log/lipaira/audit/YYYY-MM-DD.jsonl
    3. If both fail, log critical error but NEVER block execution
    
    Use for: skill executions, general API calls, read operations.
    """
    entry = _audit_log_entry(user_id, action, params, success, error)
    
    # Primary: DB write with retry
    db_success = _db_write_with_retry(user_id, action, params, success, error)
    
    # Fallback: file write if DB failed
    if not db_success:
        _write_fallback_log(entry)


def require_audit(action: str):
    """
    Decorator for critical security paths — rejects on audit failure.
    
    Use on: login, register, logout, key issuance, permission changes.
    If DB write fails after all retries, raises AuditLogError — 
    the calling endpoint must catch this and return 500.
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
                    
                    # Primary: DB write with retry
                    db_success = _db_write_with_retry(
                        user_id, action, {"endpoint": f.__name__}, success, error
                    )
                    
                    # Critical path — if DB write fails, reject the operation
                    if not db_success:
                        # Try fallback file write first
                        file_success = _write_fallback_log(entry)
                        
                        if not file_success:
                            # Both failed — this is a critical alerting condition
                            logger.error(
                                f"AUDIT CRITICAL FAILURE: user_id={user_id} action={action} "
                                f"db_error={error} — operation rejected"
                            )
                            raise AuditLogError(
                                f"Critical audit write failed for action={action}, user_id={user_id}. "
                                f"Operation rejected."
                            )
        
        return decorated
    return decorator


def replay_fallback_logs_to_db():
    """
    Replay buffered audit events from fallback files to database.
    
    Called after DB comes back online to replay any events that were
    buffered during DB outage.
    
    Returns count of events replayed.
    """
    import psycopg2
    
    fallback_dir = Path(AUDIT_FALLBACK_DIR)
    if not fallback_dir.exists():
        return 0
    
    replayed = 0
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL not set, cannot replay fallback logs")
        return 0
    
    try:
        conn = psycopg2.connect(db_url)
        
        # Process all audit log files
        for log_file in sorted(fallback_dir.glob("*-audit.log")):
            logger.info(f"Replaying fallback log: {log_file}")
            
            # Read entries (one JSON object per line)
            entries_to_replay = []
            try:
                with open(log_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                entry = json.loads(line)
                                entries_to_replay.append(entry)
                            except json.JSONDecodeError:
                                logger.warning(f"Skipping invalid JSON line in {log_file}")
            except Exception as e:
                logger.error(f"Error reading fallback log {log_file}: {e}")
                continue
            
            # Replay entries to DB
            for entry in entries_to_replay:
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO operator_audit_log 
                            (user_id, action, params, success, error, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            entry.get('user_id', ''),
                            entry.get('action', ''),
                            json.dumps({"replay": True, "payload_hash": entry.get('payload_hash', '')}),
                            entry.get('status') == 'success',
                            entry.get('error'),
                            datetime.fromisoformat(entry.get('ts', datetime.utcnow().isoformat()).replace('Z', '')) if entry.get('ts') else datetime.utcnow()
                        ))
                    replayed += 1
                except Exception as e:
                    logger.error(f"Failed to replay entry: {e}")
            
            # Mark file as replayed by renaming
            if entries_to_replay:
                replayed_file = log_file.with_suffix('.log.replayed')
                log_file.rename(replayed_file)
                logger.info(f"Marked {log_file} as replayed -> {replayed_file}")
        
        conn.commit()
        conn.close()
        
        if replayed > 0:
            logger.info(f"Replay complete: {replayed} events replayed to DB")
        
        return replayed
        
    except Exception as e:
        logger.error(f"Replay job failed: {e}")
        return 0


def rotate_old_logs():
    """
    Remove audit log files older than AUDIT_RETENTION_DAYS (90 days).
    
    Should be run daily (e.g., via cron or background task).
    """
    fallback_dir = Path(AUDIT_FALLBACK_DIR)
    if not fallback_dir.exists():
        return 0
    
    cutoff = datetime.utcnow() - timedelta(days=AUDIT_RETENTION_DAYS)
    deleted = 0
    
    for log_file in fallback_dir.glob("*-audit.log"):
        if log_file.stat().st_mtime < cutoff.timestamp():
            log_file.unlink()
            deleted += 1
            logger.info(f"Deleted old audit log: {log_file}")
    
    return deleted


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
