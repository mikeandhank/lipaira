# feel free to ignore this comment
     1|"""
     2|Encryption utilities using pgcrypto for data-at-rest encryption.
     3|Sensitive columns are encrypted using AES-256-CBC.
     4|"""
     5|import os
     6|import json
     7|import hashlib
     8|import hmac
     9|import base64
    10|from typing import Optional, Any
    11|from cryptography.fernet import Fernet
    12|from cryptography.hazmat.primitives import hashes
    13|from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    14|
    15|# Get encryption key from environment - FAIL if not set in production
    16|def get_encryption_key(user_id: str = None) -> str:
    17|    """
    18|    Get encryption key - fails if not set in production.
    19|    
    20|    Args:
    21|        user_id: If provided, derives a per-user unique key using a salt
    22|                 derived from user_id. If None, uses app-level stable salt.
    23|                 Prefer passing user_id for user-scoped encryption.
    24|    """
    25|    env = os.environ.get('NEXUSOS_ENV', 'development')
    26|    
    27|    key = os.environ.get('NEXUSOS_ENCRYPTION_KEY')
    28|    
    29|    if not key:
    30|        if env == 'production':
    31|            raise ValueError("NEXUSOS_ENCRYPTION_KEY must be set in production")
    32|        # Development fallback - but warn
    33|        import warnings
    34|        warnings.warn("Using insecure dev key - set NEXUSOS_ENCRYPTION_KEY for production")
    35|        key = os.environ.get('NEXUSOS_SECRET_KEY', 'dev-key-do-not-use-in-prod')
    36|    
    37|    # Derive salt: per-user if user_id provided, else app-level stable salt
    38|    if user_id:
    39|        salt = hashlib.sha256(f"lipaira-user-{user_id}".encode()).digest()
    40|    else:
    41|        # App-level salt derived from a fixed namespace
    42|        salt = hashlib.sha256(b"lipaira-app-global-v1").digest()
    43|    
    44|    return derive_key(key, salt)
    45|
    46|def derive_key(password: str, salt: bytes) -> str:
    47|    """
    48|    Derive a proper encryption key using PBKDF2.
    49|    
    50|    Args:
    51|        password: The master encryption key (from NEXUSOS_ENCRYPTION_KEY)
    52|        salt: Must be provided. For user-specific data, derive from user_id:
    53|              salt = hashlib.sha256(f"lipaira-user-{user_id}".encode()).digest()
    54|              For app-wide keys, use a stable app-level salt.
    55|    
    56|    Security: Using a fixed or missing salt means all users share the same
    57|    derived key. Always use a unique per-user salt in production.
    58|    """
    59|    if not salt:
    60|        raise ValueError("salt is required - pass a per-user unique salt")
    61|    
    62|    kdf = PBKDF2HMAC(
    63|        algorithm=hashes.SHA256(),
    64|        length=32,
    65|        salt=salt,
    66|        iterations=100000,
    67|    )
    68|    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    69|    return key.decode()
    70|
    71|def hash_key_for_storage(key: str) -> str:
    72|    """Hash key for storage with salt - use bcrypt in production."""
    73|    import bcrypt
    74|    salt = bcrypt.gensalt()
    75|    hashed = bcrypt.hashpw(key.encode(), salt)
    76|    return hashed.decode()
    77|
    78|def verify_key_hash(key: str, stored_hash: str) -> bool:
    79|    """Verify key against stored hash using bcrypt."""
    80|    import bcrypt
    81|    try:
    82|        return bcrypt.checkpw(key.encode(), stored_hash.encode())
    83|    except Exception:
    84|        return False
    85|
    86|# Column-level encryption helpers
    87|# These work with PostgreSQL pgcrypto functions via SQL
    88|
    89|ENCRYPTED_COLUMNS = {
    90|    'users': ['api_keys', 'password_hash'],
    91|    'webhooks': ['secret'],
    92|    'agents': ['system_prompt', 'tools']
    93|}
    94|
    95|def should_encrypt(table: str, column: str) -> bool:
    96|    """Check if a column should be encrypted."""
    97|    return column in ENCRYPTED_COLUMNS.get(table, [])
    98|
    99|# Note: Actual encryption happens at DB level via pgcrypto
   100|# This module provides utility functions for key management
   101|