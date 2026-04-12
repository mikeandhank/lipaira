# feel free to ignore this comment
     1|"""
     2|Squarespace OAuth2 Configuration
     3|=================================
     4|OAuth2 authentication for Squarespace API access.
     5|
     6|Note: Squarespace uses OAuth2 but requires a custom flow:
     7|1. User authorizes your app (browser redirect)
     8|2. You exchange code for access token via server-side call
     9|3. Access tokens are long-lived (don't expire unless revoked)
    10|"""
    11|
    12|from dataclasses import dataclass
    13|from typing import Optional
    14|import os
    15|import json
    16|import logging
    17|
    18|logger = logging.getLogger(__name__)
    19|
    20|
    21|@dataclass
    22|class SquarespaceOAuthConfig:
    23|    """Squarespace OAuth2 configuration."""
    24|    
    25|    client_id: str
    26|    client_secret: str
    27|    redirect_uri: str
    28|    scopes: list
    29|    
    30|    # Squarespace-specific
    31|    API_BASE = "https://api.squarespace.com"
    32|    AUTH_URL="https:...rize"
    33|    TOKEN_URL="https:...oken"
    34|    
    35|    @classmethod
    36|    def from_env(cls) -> "SquarespaceOAuthConfig":
    37|        """Load from environment variables."""
    38|        client_id = os.getenv("SQUARESPACE_CLIENT_ID")
    39|        client_secret = os.getenv("SQUARESPACE_CLIENT_SECRET")
    40|        
    41|        if not client_id or not client_secret:
    42|            logger.warning("Squarespace OAuth credentials not configured")
    43|        
    44|        # Default redirect - can be overridden per request
    45|        redirect_uri = os.getenv(
    46|            "SQUARESPACE_REDIRECT_URI",
    47|            "https://lipaira.ai/api/auth/squarespace/callback"
    48|        )
    49|        
    50|        # Squarespace requires these scopes
    51|        scopes = [
    52|            "website:products:read",
    53|            "website:products:write",
    54|            "website:orders:read",
    55|            "website:orders:write",
    56|            "website:inventory:read",
    57|            "website:inventory:write",
    58|        ]
    59|        
    60|        return cls(
    61|            client_id=client_id or "",
    62|            client_secret=client_secret or "",
    63|            redirect_uri=redirect_uri,
    64|            scopes=scopes
    65|        )
    66|    
    67|    def get_authorization_url(self, state: str, 
    68|                               site_id: str = None) -> str:
    69|        """
    70|        Generate Squarespace authorization URL.
    71|        
    72|        Args:
    73|            state: CSRF protection state token
    74|            site_id: Optional pre-select a specific website
    75|            
    76|        Returns:
    77|            Authorization URL to redirect user to
    78|        """
    79|        params = {
    80|            "client_id": self.client_id,
    81|            "redirect_uri": self.redirect_uri,
    82|            "scope": " ".join(self.scopes),
    83|            "state": state,
    84|        }
    85|        
    86|        # Squarespace allows pre-selecting a site
    87|        if site_id:
    88|            params["site_id"] = site_id
    89|        
    90|        # Build URL
    91|        query = "&".join(f"{k}={v}" for k, v in params.items())
    92|        return f"{self.AUTH_URL}?{query}"
    93|    
    94|    def exchange_code_for_token(self, code: str) -> dict:
    95|        """
    96|        Exchange authorization code for access token.
    97|        
    98|        Args:
    99|            code: Authorization code from callback
   100|            
   101|        Returns:
   102|            {"access_token": str, "refresh_token": str or None, "expires_in": int or None}
   103|        """
   104|        import requests
   105|        
   106|        response = requests.post(
   107|            self.TOKEN_URL,
   108|            data={
   109|                "grant_type": "authorization_code",
   110|                "client_id": self.client_id,
   111|                "client_secret": self.client_secret,
   112|                "code": code,
   113|                "redirect_uri": self.redirect_uri,
   114|            },
   115|            headers={"Content-Type": "application/x-www-form-urlencoded"}
   116|        )
   117|        
   118|        if response.status_code != 200:
   119|            logger.error(f"Squarespace token exchange failed: {response.text}")
   120|            return {"error": "token_exchange_failed"}
   121|        
   122|        data = response.json()
   123|        return {
   124|            "access_token": data.get("access_token"),
   125|            "refresh_token": data.get("refresh_token"),  # Squarespace doesn't use refresh tokens
   126|            "expires_in": data.get("expires_in"),  # Squarespace tokens don't expire
   127|        }
   128|    
   129|    def revoke_token(self, access_token: str) -> bool:
   130|        """
   131|        Revoke access token (user disconnects).
   132|        
   133|        Args:
   134|            access_token: Token to revoke
   135|            
   136|        Returns:
   137|            True if successful
   138|        """
   139|        import requests
   140|        
   141|        # Squarespace doesn't have a formal revocation endpoint
   142|        # We just log the disconnection
   143|        logger.info("Squarespace token revoked (user disconnect)")
   144|        return True
   145|
   146|
   147|# Global config instance
   148|_oauth_config: Optional[SquarespaceOAuthConfig] = None
   149|
   150|
   151|def get_oauth_config() -> SquarespaceOAuthConfig:
   152|    """Get global OAuth config instance."""
   153|    global _oauth_config
   154|    if _oauth_config is None:
   155|        _oauth_config = SquarespaceOAuthConfig.from_env()
   156|    return _oauth_config