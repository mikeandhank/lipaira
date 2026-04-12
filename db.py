# feel free to ignore this comment
     1|"""
     2|db.py — Shared database connection utilities for Lipaira.
     3|
     4|get_user_conn(user_id) — context manager that returns a psycopg2 connection
     5|scoped to the user's schema (free tier) or dedicated container (paid tier).
     6|
     7|Every file that imports this must also import psycopg2 directly.
     8|"""
     9|
    10|import os
    11|import hashlib
    12|from urllib.parse import urlparse
    13|from contextlib import contextmanager
    14|
    15|import psycopg2
    16|
    17|CONTAINER_PREFIX = "lipaira-db-"
    18|SHARED_DB_URL = os.environ.get("DATABASE_URL")
    19|if not SHARED_DB_URL:
    20|    raise RuntimeError("DATABASE_URL environment variable is required")
    21|
    22|
    23|def get_db_connection_for_user(user_id: str, tier: str):
    24|    """
    25|    Return a psycopg2 connection to the correct database for this user.
    26|
    27|    Free tier  → shared postgres, schema = u{md5(user_id)[:8]}
    28|    Paid tier  → dedicated container at {CONTAINER_PREFIX}{user_id[:8]}
    29|    """
    30|    parsed = urlparse(SHARED_DB_URL)
    31|
    32|    if tier == "paid":
    33|        # Paid: connect to dedicated container
    34|        container_host = f"{CONTAINER_PREFIX}{user_id[:8]}"
    35|        conn = psycopg2.connect(
    36|            host=container_host,
    37|            port=parsed.port or 5432,
    38|            user=parsed.username,
    39|            password=parsed.password,
    40|            dbname=parsed.path.lstrip("/") or "nexusos",
    41|        )
    42|        return conn
    43|    else:
    44|        # Free: connect to shared postgres, set search_path to user's schema
    45|        conn = psycopg2.connect(
    46|            host=parsed.hostname,
    47|            port=parsed.port or 5432,
    48|            user=parsed.username,
    49|            password=parsed.password,
    50|            dbname=parsed.path.lstrip("/") or "nexusos",
    51|        )
    52|        schema = f"u{hashlib.md5(user_id.encode()).hexdigest()[:8]}"
    53|        cur = conn.cursor()
    54|        cur.execute(f"SET search_path TO {schema}, public")
    55|        conn.commit()
    56|        return conn
    57|
    58|
    59|@contextmanager
    60|def get_user_conn(user_id: str):
    61|    """
    62|    Context manager: look up the user's tier, open the right connection,
    63|    set the search_path, and yield it to the caller.
    64|
    65|    Usage:
    66|        with get_user_conn(user_id) as conn:
    67|            cur = conn.cursor()
    68|            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    69|            ...
    70|    """
    71|    # Look up tier from shared DB
    72|    parsed = urlparse(SHARED_DB_URL)
    73|    shared_conn = psycopg2.connect(
    74|        host=parsed.hostname,
    75|        port=parsed.port or 5432,
    76|        user=parsed.username,
    77|        password=parsed.password,
    78|        dbname=parsed.path.lstrip("/") or "nexusos",
    79|    )
    80|    user_conn = None
    81|    try:
    82|        cur = shared_conn.cursor()
    83|        cur.execute(
    84|            "SELECT subscription_tier FROM users WHERE id = %s",
    85|            (user_id,)
    86|        )
    87|        row = cur.fetchone()
    88|        tier = row[0] if row else "free"
    89|        shared_conn.close()
    90|
    91|        # Open the right connection for this user
    92|        user_conn = get_db_connection_for_user(user_id, tier)
    93|        yield user_conn
    94|    finally:
    95|        if user_conn is not None and not user_conn.closed:
    96|            user_conn.close()
    97|