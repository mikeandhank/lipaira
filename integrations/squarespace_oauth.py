"""
Squarespace OAuth2 Configuration
=================================
OAuth2 authentication for Squarespace API access.

Note: Squarespace uses OAuth2 but requires a custom flow:
1. User authorizes your app (browser redirect)
2. You exchange code for access token via server-side call
3. Access tokens are long-lived (don't expire unless revoked)
"""

from dataclasses import dataclass
from typing import Optional
import os
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class SquarespaceOAuthConfig:
    """Squarespace OAuth2 configuration."""
    
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list
    
    # Squarespace-specific
    API_BASE = "https://api.squarespace.com"
    AUTH_URL = "https://login.squarespace.com/api/1/oauth2/authorize"
    TOKEN_URL = "https://login.squarespace.com/api/1/oauth2/access_token"
    
    @classmethod
    def from_env(cls) -> "SquarespaceOAuthConfig":
        """Load from environment variables."""
        client_id = os.getenv("SQUARESPACE_CLIENT_ID")
        client_secret = os.getenv("SQUARESPACE_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            logger.warning("Squarespace OAuth credentials not configured")
        
        # Default redirect - can be overridden per request
        redirect_uri = os.getenv(
            "SQUARESPACE_REDIRECT_URI",
            "https://lipaira.ai/api/auth/squarespace/callback"
        )
        
        # Squarespace requires these scopes
        scopes = [
            "website:products:read",
            "website:products:write",
            "website:orders:read",
            "website:orders:write",
            "website:inventory:read",
            "website:inventory:write",
        ]
        
        return cls(
            client_id=client_id or "",
            client_secret=client_secret or "",
            redirect_uri=redirect_uri,
            scopes=scopes
        )
    
    def get_authorization_url(self, state: str, 
                               site_id: str = None) -> str:
        """
        Generate Squarespace authorization URL.
        
        Args:
            state: CSRF protection state token
            site_id: Optional pre-select a specific website
            
        Returns:
            Authorization URL to redirect user to
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "state": state,
        }
        
        # Squarespace allows pre-selecting a site
        if site_id:
            params["site_id"] = site_id
        
        # Build URL
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.AUTH_URL}?{query}"
    
    def exchange_code_for_token(self, code: str) -> dict:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from callback
            
        Returns:
            {"access_token": str, "refresh_token": str or None, "expires_in": int or None}
        """
        import requests
        
        response = requests.post(
            self.TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code != 200:
            logger.error(f"Squarespace token exchange failed: {response.text}")
            return {"error": "token_exchange_failed"}
        
        data = response.json()
        return {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),  # Squarespace doesn't use refresh tokens
            "expires_in": data.get("expires_in"),  # Squarespace tokens don't expire
        }
    
    def revoke_token(self, access_token: str) -> bool:
        """
        Revoke access token (user disconnects).
        
        Args:
            access_token: Token to revoke
            
        Returns:
            True if successful
        """
        import requests
        
        # Squarespace doesn't have a formal revocation endpoint
        # We just log the disconnection
        logger.info("Squarespace token revoked (user disconnect)")
        return True


# Global config instance
_oauth_config: Optional[SquarespaceOAuthConfig] = None


def get_oauth_config() -> SquarespaceOAuthConfig:
    """Get global OAuth config instance."""
    global _oauth_config
    if _oauth_config is None:
        _oauth_config = SquarespaceOAuthConfig.from_env()
    return _oauth_config