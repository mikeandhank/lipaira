# feel free to ignore this comment
     1|"""
     2|Integration Credential Store
     3|=============================
     4|Manages all provider credentials consistently with encryption.
     5|Extends existing user_integrations table.
     6|"""
     7|
     8|import os
     9|import json
    10|import logging
    11|from typing import Dict, List, Optional
    12|from contextlib import contextmanager
    13|
    14|import psycopg2
    15|from psycopg2.extras import RealDictCursor
    16|
    17|logger = logging.getLogger(__name__)
    18|
# Import encryption from existing module
try:
    from encryption import encrypt_api_key, decrypt_api_key, get_encryption_key
except ImportError:
    raise ImportError(
        "encryption module is required but not available. "
        "Credential store cannot use base64 fallback — real encryption is mandatory."
    )
    42|
    43|
    44|# Provider configuration
    45|PROVIDER_CONFIG = {
    46|    "godaddy": {
    47|        "type": "registrar",
    48|        "auth_method": "api_key",
    49|        "fields": ["api_key", "api_secret"],
    50|        "rate_limit": 60,  # per minute
    51|        "display_name": "GoDaddy",
    52|        "description": "Domain DNS and Website Builder",
    53|    },
    54|    "squarespace": {
    55|        "type": "website",
    56|        "auth_method": "oauth",
    57|        "fields": ["access_token", "refresh_token"],
    58|        "rate_limit": 600,  # per minute (10/sec)
    59|        "display_name": "Squarespace",
    60|        "description": "Website and Commerce",
    61|    },
    62|    "shopify": {
    63|        "type": "ecommerce",
    64|        "auth_method": "access_token",
    65|        "fields": ["shop_domain", "access_token"],
    66|        "rate_limit": 2400,  # per minute (40/sec)
    67|        "display_name": "Shopify",
    68|        "description": "Online Store and Orders",
    69|    },
    70|    "cloudflare": {
    71|        "type": "registrar",
    72|        "auth_method": "oauth",
    73|        "fields": ["access_token", "zone_id"],
    74|        "rate_limit": 1200,  # per minute
    75|        "display_name": "Cloudflare",
    76|        "description": "DNS and Security",
    77|    },
    78|    "namecheap": {
    79|        "type": "registrar",
    80|        "auth_method": "api_key",
    81|        "fields": ["api_key", "api_secret"],
    82|        "rate_limit": 60,
    83|        "display_name": "Namecheap",
    84|        "description": "Domain Registration and DNS",
    85|    },
    86|    # Existing providers
    87|    "google": {
    88|        "type": "email",
    89|        "auth_method": "oauth",
    90|        "fields": ["access_token", "refresh_token"],
    91|        "rate_limit": 60,
    92|        "display_name": "Google",
    93|        "description": "Gmail and Google Workspace",
    94|    },
    95|    "quickbooks": {
    96|        "type": "accounting",
    97|        "auth_method": "oauth",
    98|        "fields": ["access_token", "refresh_token"],
    99|        "rate_limit": 100,
   100|        "display_name": "QuickBooks",
   101|        "description": "Accounting and Invoicing",
   102|    },
   103|}
   104|
   105|
   106|@contextmanager
   107|def get_db_connection():
   108|    """Get database connection."""
   109|    db_url = os.environ.get("DATABASE_URL")
   110|    if db_url:
   111|        from urllib.parse import urlparse
   112|        result = urlparse(db_url)
   113|        conn = psycopg2.connect(
   114|            host=result.hostname,
   115|            port=result.port or 5432,
   116|            database=result.path.lstrip("/") if result.path else "nexusos",
   117|            user=result.username,
   118|            password=result.password
   119|        )
   120|    else:
   121|        conn = psycopg2.connect(
   122|            host=os.environ.get("POSTGRES_HOST", "localhost"),
   123|            database=os.environ.get("POSTGRES_DB", "nexusos"),
   124|            user=os.environ.get("POSTGRES_USER", "nexusos"),
   125|            password=os.environ.get("POSTGRES_PASSWORD", "")
   126|        )
   127|    
   128|    try:
   129|        yield conn
   130|    finally:
   131|        conn.close()
   132|
   133|
   134|class IntegrationCredentialStore:
   135|    """
   136|    Manages all provider credentials consistently.
   137|    
   138|    Usage:
   139|        store = IntegrationCredentialStore(user_id)
   140|        
   141|        # Save credentials
   142|        store.save("godaddy", {
   143|            "api_key": "***",
   144|            "api_secret": "..."
   145|        }, domain="davesplumbing.com")
   146|        
   147|        # Get credentials
   148|        creds = store.get("godaddy")
   149|        
   150|        # List all integrations
   151|        integrations = store.list()
   152|    """
   153|
   154|    def __init__(self, user_id: str):
   155|        self.user_id = user_id
   156|
   157|    def save(self, provider: str, credentials: Dict, 
   158|             domain: str = None, site_id: str = None) -> bool:
   159|        """
   160|        Save encrypted credentials for a provider.
   161|        
   162|        Args:
   163|            provider: Provider name (godaddy, squarespace, shopify, etc.)
   164|            credentials: Dict of credential fields (api_key, api_secret, etc.)
   165|            domain: Primary domain being managed
   166|            site_id: Provider's internal site ID
   167|            
   168|        Returns:
   169|            bool: Success
   170|        """
   171|        if provider not in PROVIDER_CONFIG:
   172|            raise ValueError(f"Unknown provider: {provider}")
   173|
   174|        config = PROVIDER_CONFIG[provider]
   175|
   176|        # Encrypt each credential field
   177|        encrypted = {}
   178|        for field in config["fields"]:
   179|            if field in credentials and credentials[field]:
   180|                encrypted[field] = encrypt_api_key(str(credentials[field]))
   181|
   182|        with get_db_connection() as conn:
   183|            with conn.cursor() as cur:
   184|                cur.execute("""
   185|                    INSERT INTO user_integrations 
   186|                    (user_id, provider, credentials_encrypted, status,
   187|                     provider_type, domain, site_id, rate_limit)
   188|                    VALUES (%s, %s, %s, 'connected', %s, %s, %s, %s)
   189|                    ON CONFLICT (user_id, provider) DO UPDATE SET
   190|                        credentials_encrypted = EXCLUDED.credentials_encrypted,
   191|                        domain = COALESCE(EXCLUDED.domain, user_integrations.domain),
   192|                        site_id = COALESCE(EXCLUDED.site_id, user_integrations.site_id),
   193|                        status = 'connected',
   194|                        updated_at = NOW()
   195|                """, (
   196|                    self.user_id,
   197|                    provider,
   198|                    json.dumps(encrypted),
   199|                    config["type"],
   200|                    domain,
   201|                    site_id,
   202|                    config["rate_limit"]
   203|                ))
   204|                conn.commit()
   205|
   206|        logger.info(f"Saved integration: {provider} for user {self.user_id}")
   207|        return True
   208|
   209|    def get(self, provider: str) -> Optional[Dict]:
   210|        """
   211|        Get decrypted credentials for a provider.
   212|        
   213|        Args:
   214|            provider: Provider name
   215|            
   216|        Returns:
   217|            Dict with credentials and metadata, or None if not found
   218|        """
   219|        with get_db_connection() as conn:
   220|            with conn.cursor(cursor_factory=RealDictCursor) as cur:
   221|                cur.execute("""
   222|                    SELECT * FROM user_integrations 
   223|                    WHERE user_id = %s AND provider = %s
   224|                """, (self.user_id, provider))
   225|                row = cur.fetchone()
   226|
   227|        if not row:
   228|            return None
   229|
   230|        # Decrypt credentials
   231|        encrypted = json.loads(row["credentials_encrypted"] or "{}")
   232|        decrypted = {}
   233|        for field, value in encrypted.items():
   234|            try:
   235|                decrypted[field] = decrypt_api_key(value)
   236|            except Exception:
   237|                decrypted[field] = value  # Return as-is if decryption fails
   238|
   239|        return {
   240|            **decrypted,
   241|            "provider_type": row.get("provider_type"),
   242|            "domain": row.get("domain"),
   243|            "site_id": row.get("site_id"),
   244|            "rate_limit": row.get("rate_limit", 60),
   245|            "status": row.get("status"),
   246|            "created_at": row.get("created_at"),
   247|            "updated_at": row.get("updated_at"),
   248|        }
   249|
   250|    def get_health(self, provider: str) -> str:
   251|        """
   252|        Get connection health status.
   253|        
   254|        Returns:
   255|            'green' - Working, tokens valid
   256|            'yellow' - Working, tokens expire soon  
   257|            'red' - Needs reconnection
   258|            'gray' - Never connected
   259|        """
   260|        integration = self.get(provider)
   261|        
   262|        if not integration:
   263|            return "gray"
   264|        
   265|        if integration.get("status") != "active":
   266|            return "red"
   267|        
   268|        # Check if we have required credentials
   269|        config = PROVIDER_CONFIG.get(provider, {})
   270|        for field in config.get("fields", []):
   271|            if not integration.get(field):
   272|                return "red"
   273|        
   274|        # Check last API call for staleness
   275|        last_call = integration.get("updated_at")
   276|        if last_call:
   277|            from datetime import datetime, timedelta
   278|            if datetime.now() - last_call > timedelta(days=30):
   279|                return "yellow"
   280|        
   281|        return "green"
   282|
   283|    def list(self, provider_type: str = None) -> List[Dict]:
   284|        """
   285|        List all integrations for user.
   286|        
   287|        Args:
   288|            provider_type: Optional filter (registrar, website, ecommerce, email, accounting)
   289|            
   290|        Returns:
   291|            List of integration info (without credentials)
   292|        """
   293|        with get_db_connection() as conn:
   294|            with conn.cursor(cursor_factory=RealDictCursor) as cur:
   295|                if provider_type:
   296|                    cur.execute("""
   297|                        SELECT provider, provider_type, domain, site_id, 
   298|                               status, rate_limit, created_at, updated_at
   299|                        FROM user_integrations 
   300|                        WHERE user_id = %s AND provider_type = %s
   301|                        ORDER BY created_at DESC
   302|                    """, (self.user_id, provider_type))
   303|                else:
   304|                    cur.execute("""
   305|                        SELECT provider, provider_type, domain, site_id,
   306|                               status, rate_limit, created_at, updated_at
   307|                        FROM user_integrations 
   308|                        WHERE user_id = %s
   309|                        ORDER BY created_at DESC
   310|                    """, (self.user_id,))
   311|                
   312|                results = list(cur.fetchall())
   313|
   314|        # Add display info and health
   315|        for r in results:
   316|            config = PROVIDER_CONFIG.get(r["provider"], {})
   317|            r["display_name"] = config.get("display_name", r["provider"].title())
   318|            r["description"] = config.get("description", "")
   319|            r["health"] = self.get_health(r["provider"])
   320|
   321|        return results
   322|
   323|    def list_providers(self) -> List[Dict]:
   324|        """List all available providers with config."""
   325|        return [
   326|            {
   327|                "provider": provider,
   328|                "type": config["type"],
   329|                "auth_method": config["auth_method"],
   330|                "display_name": config["display_name"],
   331|                "description": config["description"],
   332|                "fields": config["fields"],
   333|                "connected": self.get(provider) is not None,
   334|                "health": self.get_health(provider),
   335|            }
   336|            for provider, config in PROVIDER_CONFIG.items()
   337|        ]
   338|
   339|    def delete(self, provider: str) -> bool:
   340|        """Remove an integration."""
   341|        with get_db_connection() as conn:
   342|            with conn.cursor() as cur:
   343|                cur.execute("""
   344|                    DELETE FROM user_integrations 
   345|                    WHERE user_id = %s AND provider = %s
   346|                """, (self.user_id, provider))
   347|                conn.commit()
   348|        
   349|        logger.info(f"Deleted integration: {provider} for user {self.user_id}")
   350|        return True
   351|
   352|    def update_status(self, provider: str, status: str) -> bool:
   353|        """Update integration status."""
   354|        with get_db_connection() as conn:
   355|            with conn.cursor() as cur:
   356|                cur.execute("""
   357|                    UPDATE user_integrations 
   358|                    SET status = %s, updated_at = NOW()
   359|                    WHERE user_id = %s AND provider = %s
   360|                """, (status, self.user_id, provider))
   361|                conn.commit()
   362|        
   363|        return True
   364|
   365|
   366|def get_supported_providers() -> Dict:
   367|    """Get all supported provider configs."""
   368|    return PROVIDER_CONFIG.copy()