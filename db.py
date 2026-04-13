# feel free to ignore this comment
"""
db.py — Shared database connection utilities for Lipaira.

get_user_conn(user_id) — context manager that returns a psycopg2 connection
scoped to the user's schema (free tier) or dedicated container (paid tier).

Every file that imports this must also import psycopg2 directly.
"""

import os
import hashlib
from urllib.parse import urlparse
from contextlib import contextmanager

import psycopg2

CONTAINER_PREFIX = "lipaira-db-"
SHARED_DB_URL = os.environ.get("DATABASE_URL")
if not SHARED_DB_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")


def get_db_connection_for_user(user_id: str, tier: str):
    """
    Return a psycopg2 connection to the correct database for this user.

    Free tier  → shared postgres, schema = u{md5(user_id)[:8]}
    Paid tier  → dedicated container at {CONTAINER_PREFIX}{user_id[:8]}
    """
    parsed = urlparse(SHARED_DB_URL)

    if tier == "paid":
        # Paid: connect to dedicated container
        container_host = f"{CONTAINER_PREFIX}{user_id[:8]}"
        conn = psycopg2.connect(
            host=container_host,
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            dbname=parsed.path.lstrip("/") or "nexusos",
        )
        return conn
    else:
        # Free: connect to shared postgres, set search_path to user's schema
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            dbname=parsed.path.lstrip("/") or "nexusos",
        )
        schema = f"u{hashlib.md5(user_id.encode()).hexdigest()[:8]}"
        cur = conn.cursor()
        # Diagnosis: SET search_path used string interpolation which is SQL injection risk.
        # Fix: use parameterized query which psycopg2 handles safely for SET statements.
        cur.execute("SET search_path TO %s, public", (schema,))
        conn.commit()
        return conn


@contextmanager
def get_user_conn(user_id: str):
    """
    Context manager: look up the user's tier, open the right connection,
    set the search_path, and yield it to the caller.

    Usage:
        with get_user_conn(user_id) as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            ...
    """
    # Look up tier from shared DB
    parsed = urlparse(SHARED_DB_URL)
    shared_conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        dbname=parsed.path.lstrip("/") or "nexusos",
    )
    user_conn = None
    try:
        cur = shared_conn.cursor()
        cur.execute(
            "SELECT subscription_tier FROM users WHERE id = %s",
            (user_id,)
        )
        row = cur.fetchone()
        tier = row[0] if row else "free"
        shared_conn.close()

        # Open the right connection for this user
        user_conn = get_db_connection_for_user(user_id, tier)
        yield user_conn
    finally:
        if user_conn is not None and not user_conn.closed:
            user_conn.close()
