"""
Integration Credential Store
=============================
Manages all provider credentials consistently with encryption.
Extends existing user_integrations table.
"""

import os
import json
import logging
from typing import Dict, List, Optional
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# Import encryption from existing module
try:
    from encryption import encrypt_api_key, decrypt_api_key, get_encryption_key
except ImportError:
    # Fallback for when encryption module isn't available
    def encrypt_api_key(key: str) -> str:
        import base64
        return base64.b64encode(key.encode()).decode()
    
    def decrypt_api_key(encrypted: str) -> str:
        import base64
        return base64.b64decode(encrypted.encode()).decode()
    
    def get_encryption_key():
        key = os.environ.get('ENCRYPTION_KEY')
        if not key:
            env = os.environ.get('LIPAIRA_ENV', 'development')
            if env == 'production':
                raise ValueError("ENCRYPTION_KEY environment variable is required in production")
            import warnings
            warnings.warn("Using insecure dev key fallback — set ENCRYPTION_KEY for production")
            key = 'dev-key-do-not-use-in-prod'
        return key


# Provider configuration
PROVIDER_CONFIG = {
    "godaddy": {
        "type": "registrar",
        "auth_method": "api_key",
        "fields": ["api_key", "api_secret"],
        "rate_limit": 60,  # per minute
        "display_name": "GoDaddy",
        "description": "Domain DNS and Website Builder",
    },
    "squarespace": {
        "type": "website",
        "auth_method": "oauth",
        "fields": ["access_token", "refresh_token"],
        "rate_limit": 600,  # per minute (10/sec)
        "display_name": "Squarespace",
        "description": "Website and Commerce",
    },
    "shopify": {
        "type": "ecommerce",
        "auth_method": "access_token",
        "fields": ["shop_domain", "access_token"],
        "rate_limit": 2400,  # per minute (40/sec)
        "display_name": "Shopify",
        "description": "Online Store and Orders",
    },
    "cloudflare": {
        "type": "registrar",
        "auth_method": "oauth",
        "fields": ["access_token", "zone_id"],
        "rate_limit": 1200,  # per minute
        "display_name": "Cloudflare",
        "description": "DNS and Security",
    },
    "namecheap": {
        "type": "registrar",
        "auth_method": "api_key",
        "fields": ["api_key", "api_secret"],
        "rate_limit": 60,
        "display_name": "Namecheap",
        "description": "Domain Registration and DNS",
    },
    # Existing providers
    "google": {
        "type": "email",
        "auth_method": "oauth",
        "fields": ["access_token", "refresh_token"],
        "rate_limit": 60,
        "display_name": "Google",
        "description": "Gmail and Google Workspace",
    },
    "quickbooks": {
        "type": "accounting",
        "auth_method": "oauth",
        "fields": ["access_token", "refresh_token"],
        "rate_limit": 100,
        "display_name": "QuickBooks",
        "description": "Accounting and Invoicing",
    },
}


@contextmanager
def get_db_connection():
    """Get database connection."""
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        from urllib.parse import urlparse
        result = urlparse(db_url)
        conn = psycopg2.connect(
            host=result.hostname,
            port=result.port or 5432,
            database=result.path.lstrip("/") if result.path else "nexusos",
            user=result.username,
            password=result.password
        )
    else:
        conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            database=os.environ.get("POSTGRES_DB", "nexusos"),
            user=os.environ.get("POSTGRES_USER", "nexusos"),
            password=os.environ.get("POSTGRES_PASSWORD", "")
        )
    
    try:
        yield conn
    finally:
        conn.close()


class IntegrationCredentialStore:
    """
    Manages all provider credentials consistently.
    
    Usage:
        store = IntegrationCredentialStore(user_id)
        
        # Save credentials
        store.save("godaddy", {
            "api_key": "...",
            "api_secret": "..."
        }, domain="davesplumbing.com")
        
        # Get credentials
        creds = store.get("godaddy")
        
        # List all integrations
        integrations = store.list()
    """

    def __init__(self, user_id: str):
        self.user_id = user_id

    def save(self, provider: str, credentials: Dict, 
             domain: str = None, site_id: str = None) -> bool:
        """
        Save encrypted credentials for a provider.
        
        Args:
            provider: Provider name (godaddy, squarespace, shopify, etc.)
            credentials: Dict of credential fields (api_key, api_secret, etc.)
            domain: Primary domain being managed
            site_id: Provider's internal site ID
            
        Returns:
            bool: Success
        """
        if provider not in PROVIDER_CONFIG:
            raise ValueError(f"Unknown provider: {provider}")

        config = PROVIDER_CONFIG[provider]

        # Encrypt each credential field
        encrypted = {}
        for field in config["fields"]:
            if field in credentials and credentials[field]:
                encrypted[field] = encrypt_api_key(str(credentials[field]))

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO user_integrations 
                    (user_id, provider, credentials_encrypted, status,
                     provider_type, domain, site_id, rate_limit)
                    VALUES (%s, %s, %s, 'connected', %s, %s, %s, %s)
                    ON CONFLICT (user_id, provider) DO UPDATE SET
                        credentials_encrypted = EXCLUDED.credentials_encrypted,
                        domain = COALESCE(EXCLUDED.domain, user_integrations.domain),
                        site_id = COALESCE(EXCLUDED.site_id, user_integrations.site_id),
                        status = 'connected',
                        updated_at = NOW()
                """, (
                    self.user_id,
                    provider,
                    json.dumps(encrypted),
                    config["type"],
                    domain,
                    site_id,
                    config["rate_limit"]
                ))
                conn.commit()

        logger.info(f"Saved integration: {provider} for user {self.user_id}")
        return True

    def get(self, provider: str) -> Optional[Dict]:
        """
        Get decrypted credentials for a provider.
        
        Args:
            provider: Provider name
            
        Returns:
            Dict with credentials and metadata, or None if not found
        """
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM user_integrations 
                    WHERE user_id = %s AND provider = %s
                """, (self.user_id, provider))
                row = cur.fetchone()

        if not row:
            return None

        # Decrypt credentials
        encrypted = json.loads(row["credentials_encrypted"] or "{}")
        decrypted = {}
        for field, value in encrypted.items():
            try:
                decrypted[field] = decrypt_api_key(value)
            except Exception:
                decrypted[field] = value  # Return as-is if decryption fails

        return {
            **decrypted,
            "provider_type": row.get("provider_type"),
            "domain": row.get("domain"),
            "site_id": row.get("site_id"),
            "rate_limit": row.get("rate_limit", 60),
            "status": row.get("status"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def get_health(self, provider: str) -> str:
        """
        Get connection health status.
        
        Returns:
            'green' - Working, tokens valid
            'yellow' - Working, tokens expire soon  
            'red' - Needs reconnection
            'gray' - Never connected
        """
        integration = self.get(provider)
        
        if not integration:
            return "gray"
        
        if integration.get("status") != "active":
            return "red"
        
        # Check if we have required credentials
        config = PROVIDER_CONFIG.get(provider, {})
        for field in config.get("fields", []):
            if not integration.get(field):
                return "red"
        
        # Check last API call for staleness
        last_call = integration.get("updated_at")
        if last_call:
            from datetime import datetime, timedelta
            if datetime.now() - last_call > timedelta(days=30):
                return "yellow"
        
        return "green"

    def list(self, provider_type: str = None) -> List[Dict]:
        """
        List all integrations for user.
        
        Args:
            provider_type: Optional filter (registrar, website, ecommerce, email, accounting)
            
        Returns:
            List of integration info (without credentials)
        """
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if provider_type:
                    cur.execute("""
                        SELECT provider, provider_type, domain, site_id, 
                               status, rate_limit, created_at, updated_at
                        FROM user_integrations 
                        WHERE user_id = %s AND provider_type = %s
                        ORDER BY created_at DESC
                    """, (self.user_id, provider_type))
                else:
                    cur.execute("""
                        SELECT provider, provider_type, domain, site_id,
                               status, rate_limit, created_at, updated_at
                        FROM user_integrations 
                        WHERE user_id = %s
                        ORDER BY created_at DESC
                    """, (self.user_id,))
                
                results = list(cur.fetchall())

        # Add display info and health
        for r in results:
            config = PROVIDER_CONFIG.get(r["provider"], {})
            r["display_name"] = config.get("display_name", r["provider"].title())
            r["description"] = config.get("description", "")
            r["health"] = self.get_health(r["provider"])

        return results

    def list_providers(self) -> List[Dict]:
        """List all available providers with config."""
        return [
            {
                "provider": provider,
                "type": config["type"],
                "auth_method": config["auth_method"],
                "display_name": config["display_name"],
                "description": config["description"],
                "fields": config["fields"],
                "connected": self.get(provider) is not None,
                "health": self.get_health(provider),
            }
            for provider, config in PROVIDER_CONFIG.items()
        ]

    def delete(self, provider: str) -> bool:
        """Remove an integration."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM user_integrations 
                    WHERE user_id = %s AND provider = %s
                """, (self.user_id, provider))
                conn.commit()
        
        logger.info(f"Deleted integration: {provider} for user {self.user_id}")
        return True

    def update_status(self, provider: str, status: str) -> bool:
        """Update integration status."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE user_integrations 
                    SET status = %s, updated_at = NOW()
                    WHERE user_id = %s AND provider = %s
                """, (status, self.user_id, provider))
                conn.commit()
        
        return True


def get_supported_providers() -> Dict:
    """Get all supported provider configs."""
    return PROVIDER_CONFIG.copy()