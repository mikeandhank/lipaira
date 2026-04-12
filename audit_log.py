# feel free to ignore this comment
     1|"""
     2|Audit logging for skill executions and security-critical actions.
     3|Every consequential action gets logged for security and compliance.
     4|
     5|Two tiers:
     6|- Critical (require_audit): login, key issuance, permission changes.
     7|  Fails the operation if DB audit write fails. Raises AuditLogError.
     8|- Non-critical (log_audit): skill executions, general API calls.
     9|  Falls back to file + stderr on failure. Never blocks execution.
    10|
    11|Note: Fallback logs to /var/log/lipaira/audit_fallback.jsonl.
    12|These logs are ephemeral — they exist only inside the container and are
    13|lost on container restart unless /var/log/lipaira is mounted as a volume.
    14|"""
    15|
    16|import json
    17|import logging
    18|import os
    19|import uuid
    20|from datetime import datetime
    21|from functools import wraps
    22|from typing import Optional
    23|
    24|logger = logging.getLogger(__name__)
    25|
    26|
    27|class AuditLogError(Exception):
    28|    """Raised when a critical audit log write fails and the operation must be rejected."""
    29|    pass
    30|
    31|
    32|def _write_fallback_log(entry: dict, fallback_path: str = "/var/log/lipaira/audit_fallback.jsonl"):
    33|    """
    34|    Write audit entry to fallback file when DB is unavailable.
    35|    
    36|    Note: These logs are ephemeral — stored inside the container.
    37|    They are lost on container restart unless /var/log/lipaira is
    38|    mounted as a persistent volume from the host.
    39|    """
    40|    try:
    41|        os.makedirs(os.path.dirname(fallback_path), exist_ok=True)
    42|        with open(fallback_path, "a") as f:
    43|            f.write(json.dumps(entry) + "\n")
    44|    except Exception:
    45|        pass  # Last resort: at least we tried the file
    46|
    47|
    48|def _audit_log_entry(user_id: str, action: str, params: Optional[dict] = None,
    49|                     success: bool = True, error: Optional[str] = None) -> dict:
    50|    """Build a standard audit log entry."""
    51|    return {
    52|        "id": str(uuid.uuid4()),
    53|        "user_id": user_id,
    54|        "action": action,
    55|        "params": params or {},
    56|        "success": success,
    57|        "error": error,
    58|        "timestamp": datetime.utcnow().isoformat() + "Z",
    59|    }
    60|
    61|
    62|def log_audit(user_id: str, action: str, params: Optional[dict] = None,
    63|              success: bool = True, error: Optional[str] = None):
    64|    """
    65|    Non-critical audit log — continues on failure with fallback.
    66|    
    67|    Use for: skill executions, general API calls, read operations.
    68|    If DB write fails, writes to /var/log/lipaira/audit_fallback.jsonl
    69|    and logs to stderr. Does not block the calling code.
    70|    """
    71|    entry = _audit_log_entry(user_id, action, params, success, error)
    72|    
    73|    try:
    74|        import psycopg2
    75|        db_url = os.environ.get('DATABASE_URL')
    76|        if not db_url:
    77|            raise RuntimeError("DATABASE_URL environment variable is required")
    78|        
    79|        conn = psycopg2.connect(db_url)
    80|        with conn.cursor() as cur:
    81|            cur.execute("""
    82|                INSERT INTO operator_audit_log 
    83|                (user_id, action, params, success, error, created_at)
    84|                VALUES (%s, %s, %s, %s, %s, %s)
    85|            """, (user_id, action, json.dumps(params or {}),
    86|                  success, error, datetime.utcnow()))
    87|            conn.commit()
    88|        conn.close()
    89|        logger.info(f"Audit log: [{action}] {user_id} success={success}")
    90|        
    91|    except Exception as e:
    92|        # Fallback: write to file + stderr. Never block.
    93|        logger.warning(
    94|            f"AUDIT FALLBACK: user_id={user_id} action={action} "
    95|            f"timestamp={entry['timestamp']} error={str(e)}"
    96|        )
    97|        _write_fallback_log(entry)
    98|
    99|
   100|def require_audit(action: str):
   101|    """
   102|    Decorator for critical security paths — rejects on audit failure.
   103|    
   104|    Use on: login, register, logout, key issuance, permission changes.
   105|    If DB write fails, raises AuditLogError — the calling endpoint
   106|    must catch this and return 500.
   107|    
   108|    Usage:
   109|        @app.route('/api/auth/login', methods=['POST'])
   110|        @require_audit("login")
   111|        def login():
   112|            ...
   113|    """
   114|    def decorator(f):
   115|        @wraps(f)
   116|        def decorated(*args, **kwargs):
   117|            # Extract user_id from Flask g object if available
   118|            user_id = None
   119|            try:
   120|                from flask import g
   121|                user_id = getattr(g, 'user_id', None)
   122|            except ImportError:
   123|                pass
   124|            
   125|            success = True
   126|            error = None
   127|            result = None
   128|            
   129|            try:
   130|                result = f(*args, **kwargs)
   131|                return result
   132|            except AuditLogError:
   133|                raise  # Already handled
   134|            except Exception as e:
   135|                success = False
   136|                error = str(e)
   137|                raise
   138|            finally:
   139|                if user_id:
   140|                    entry = _audit_log_entry(user_id, action, {"endpoint": f.__name__}, success, error)
   141|                    try:
   142|                        import psycopg2
   143|                        db_url = os.environ.get('DATABASE_URL')
   144|                        if not db_url:
   145|                            raise RuntimeError("DATABASE_URL required")
   146|                        
   147|                        conn = psycopg2.connect(db_url)
   148|                        with conn.cursor() as cur:
   149|                            cur.execute("""
   150|                                INSERT INTO operator_audit_log 
   151|                                (user_id, action, params, success, error, created_at)
   152|                                VALUES (%s, %s, %s, %s, %s, %s)
   153|                            """, (user_id, action, json.dumps({"endpoint": f.__name__}),
   154|                                  success, error, datetime.utcnow()))
   155|                            conn.commit()
   156|                        conn.close()
   157|                    except Exception as db_e:
   158|                        # Critical path — DB write MUST succeed or we reject
   159|                        logger.error(
   160|                            f"AUDIT CRITICAL FAILURE: user_id={user_id} action={action} "
   161|                            f"db_error={str(db_e)} — operation rejected"
   162|                        )
   163|                        raise AuditLogError(
   164|                            f"Critical audit write failed for action={action}, user_id={user_id}. "
   165|                            f"Operation rejected. DB error: {db_e}"
   166|                        )
   167|        
   168|        return decorated
   169|    return decorator
   170|
   171|
   172|# Alias for backward compatibility
   173|def log_skill_execution(user_id: str, skill_name: str,
   174|                        params: dict, result: dict,
   175|                        approved_by: str = "user"):
   176|    """Legacy alias — maps to log_audit with skill_name as action."""
   177|    log_audit(
   178|        user_id=user_id,
   179|        action=f"skill:{skill_name}",
   180|        params={"params": params, "result": result, "approved_by": approved_by},
   181|        success=True,
   182|    )
   183|
   184|
   185|def create_audit_log_table():
   186|    """Create the audit log table if it doesn't exist."""
   187|    import psycopg2
   188|    
   189|    try:
   190|        db_url = os.environ.get('DATABASE_URL')
   191|        if not db_url:
   192|            raise RuntimeError("DATABASE_URL environment variable is required")
   193|        conn = psycopg2.connect(db_url)
   194|        
   195|        with conn.cursor() as cur:
   196|            # Check if action column exists (schema migration)
   197|            cur.execute("""
   198|                SELECT column_name FROM information_schema.columns
   199|                WHERE table_name = 'operator_audit_log' AND column_name = 'action'
   200|            """)
   201|            has_action = cur.fetchone() is not None
   202|            
   203|            if has_action:
   204|                # New schema — action + success + error
   205|                cur.execute("""
   206|                    CREATE TABLE IF NOT EXISTS operator_audit_log (
   207|                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
   208|                        user_id VARCHAR(255) NOT NULL,
   209|                        business_id UUID,
   210|                        action VARCHAR(100),
   211|                        skill_name VARCHAR(100),
   212|                        params JSONB,
   213|                        result JSONB,
   214|                        success BOOLEAN DEFAULT true,
   215|                        error TEXT,
   216|                        approved_by VARCHAR(50) DEFAULT 'user',
   217|                        created_at TIMESTAMP DEFAULT NOW()
   218|                    );
   219|                """)
   220|            else:
   221|                # Original schema — skill_name based
   222|                cur.execute("""
   223|                    CREATE TABLE IF NOT EXISTS operator_audit_log (
   224|                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
   225|                        user_id VARCHAR(255) NOT NULL,
   226|                        business_id UUID,
   227|                        skill_name VARCHAR(100) NOT NULL,
   228|                        params JSONB,
   229|                        result JSONB,
   230|                        approved_by VARCHAR(50) DEFAULT 'user',
   231|                        created_at TIMESTAMP DEFAULT NOW()
   232|                    );
   233|                """)
   234|            
   235|            cur.execute("""
   236|                CREATE INDEX IF NOT EXISTS idx_audit_user 
   237|                ON operator_audit_log(user_id, created_at DESC)
   238|            """)
   239|            conn.commit()
   240|        
   241|        conn.close()
   242|        logger.info("Audit log table ready")
   243|    except Exception as e:
   244|        logger.warning(f"Failed to create audit log table: {e}")
   245|