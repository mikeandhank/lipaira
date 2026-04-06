"""Base utilities for all skills.

Security model: Skills fetch their own OAuth tokens from the database.
Tokens NEVER travel through workflow definitions.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Any
import requests

log = logging.getLogger(__name__)


def get_integration_tokens(
    user_id: str,
    business_id: str | None,
    provider: str
) -> dict:
    """Fetch OAuth tokens for a user's integration with auto-refresh.
    
    Args:
        user_id: The user's ID
        business_id: Optional business ID for multi-business users
        provider: Integration provider name (e.g., 'quickbooks', 'google')
    
    Returns:
        Dict with access_token, refresh_token, expires_at, metadata
    
    Raises:
        ValueError: If integration not connected or token expired and can't refresh
    """
    import psycopg2
    
    db_url = os.environ.get(
        'DATABASE_URL',
        'postgresql://nexusos:ChangeMe123!@postgres:5432/nexusos'
    )
    conn = psycopg2.connect(db_url)
    
    with conn.cursor() as cur:
        cur.execute("""
            SELECT access_token, refresh_token, 
                   expires_at, extra, scopes, credentials_encrypted
            FROM user_integrations
            WHERE user_id = %s
              AND provider = %s
              AND (business_id = %s OR business_id IS NULL)
            ORDER BY business_id NULLS LAST
            LIMIT 1
        """, (user_id, provider, business_id))
        
        row = cur.fetchone()
        conn.close()
        
        if not row:
            raise ValueError(
                f"Integration '{provider}' not connected. "
                f"Connect it from the Dashboard."
            )
        
        access_token, refresh_token, expires_at, extra, scopes, credentials_encrypted = row
        
        # Handle extra/metadata - could be string (JSON), dict, or None
        metadata = {}
        if extra:
            if isinstance(extra, dict):
                metadata = extra
            else:
                import json
                try:
                    metadata = json.loads(extra) if isinstance(extra, str) else {}
                except:
                    metadata = {}
        
        # Add credentials from credentials_encrypted if present
        if credentials_encrypted:
            if isinstance(credentials_encrypted, dict):
                metadata.update(credentials_encrypted)
            else:
                import json
                try:
                    creds = json.loads(credentials_encrypted) if isinstance(credentials_encrypted, str) else {}
                    metadata.update(creds)
                except:
                    pass
        
        # Add scopes to metadata if present
        if scopes:
            metadata['scopes'] = scopes
        
        # Check if token is expired or expiring within 5 minutes
        if expires_at:
            # Handle both datetime and string
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            
            buffer = timedelta(minutes=5)
            # Strip timezone info for safe comparison
            expires_naive = expires_at.replace(tzinfo=None) if expires_at.tzinfo else expires_at
            if expires_naive - buffer < datetime.utcnow():
                # Token expired or expiring soon — try to refresh
                if not refresh_token:
                    raise ValueError(
                        f"{provider} token expired and no refresh token. "
                        f"Please reconnect from the Dashboard."
                    )
                
                # Try to refresh
                refreshed = _refresh_oauth_token(provider, refresh_token)
                if refreshed:
                    # Save new token to DB
                    _save_refreshed_token(
                        user_id, provider, business_id, 
                        refreshed, access_token, expires_at
                    )
                    access_token = refreshed.get("access_token")
                    if refreshed.get("expires_in"):
                        expires_at = datetime.utcnow() + timedelta(
                            seconds=refreshed["expires_in"]
                        )
                    # Get new refresh token if provided
                    refresh_token = refreshed.get("refresh_token") or refresh_token
                else:
                    raise ValueError(
                        f"{provider} token refresh failed. "
                        f"Please reconnect from the Dashboard."
                    )
        
        # Add OAuth client credentials from environment
        metadata['client_id'] = os.environ.get(f'{provider.upper()}_CLIENT_ID', '')
        metadata['client_secret'] = os.environ.get(f'{provider.upper()}_CLIENT_SECRET', '')
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "metadata": metadata
        }


def _refresh_oauth_token(provider: str, refresh_token: str) -> dict | None:
    """Refresh an OAuth access token using the refresh token."""
    
    # Granular Google providers all use the same endpoint and credentials
    GOOGLE_PROVIDERS = {'google', 'gmail', 'google_calendar', 'google_drive', 'google_business'}
    
    REFRESH_ENDPOINTS = {
        "google": "https://oauth2.googleapis.com/token",
        "gmail": "https://oauth2.googleapis.com/token",
        "google_calendar": "https://oauth2.googleapis.com/token",
        "google_drive": "https://oauth2.googleapis.com/token",
        "google_business": "https://oauth2.googleapis.com/token",
        "microsoft": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "quickbooks": "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
    }
    
    # Granular Google providers share the same client credentials
    def _google_id(): return os.environ.get("GOOGLE_CLIENT_ID")
    def _google_sec(): return os.environ.get("GOOGLE_CLIENT_SECRET")
    
    CLIENT_IDS = {
        "google": _google_id(),
        "gmail": _google_id(),
        "google_calendar": _google_id(),
        "google_drive": _google_id(),
        "google_business": _google_id(),
        "microsoft": os.environ.get("MICROSOFT_CLIENT_ID"),
        "quickbooks": os.environ.get("QUICKBOOKS_CLIENT_ID"),
    }
    
    CLIENT_SECRETS = {
        "google": _google_sec(),
        "gmail": _google_sec(),
        "google_calendar": _google_sec(),
        "google_drive": _google_sec(),
        "google_business": _google_sec(),
        "microsoft": os.environ.get("MICROSOFT_CLIENT_SECRET"),
        "quickbooks": os.environ.get("QUICKBOOKS_CLIENT_SECRET"),
    }
    
    endpoint = REFRESH_ENDPOINTS.get(provider)
    if not endpoint:
        log.warning(f"No refresh endpoint for provider '{provider}'")
        return None
    
    try:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_IDS.get(provider, ""),
            "client_secret": CLIENT_SECRETS.get(provider, ""),
        }
        
        resp = requests.post(endpoint, data=data, timeout=10)
        
        if resp.ok:
            log.info(f"Token refreshed successfully for {provider}")
            return resp.json()
        else:
            log.error(f"Token refresh failed for {provider}: {resp.status_code} {resp.text[:200]}")
            return None
    
    except Exception as e:
        log.error(f"Token refresh exception for {provider}: {e}")
        return None


def _save_refreshed_token(
    user_id: str, 
    provider: str,
    business_id: str | None,
    token_data: dict,
    old_access_token: str,
    old_expires_at: datetime
):
    """Save refreshed access token back to DB."""
    import psycopg2
    
    new_access_token = token_data.get("access_token")
    expires_in = token_data.get("expires_in", 3600)
    new_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    new_refresh_token = token_data.get("refresh_token")
    
    db_url = os.environ.get(
        'DATABASE_URL',
        'postgresql://nexusos:ChangeMe123!@postgres:5432/nexusos'
    )
    conn = psycopg2.connect(db_url)
    
    try:
        with conn.cursor() as cur:
            if new_refresh_token:
                cur.execute("""
                    UPDATE user_integrations
                    SET access_token = %s,
                        refresh_token = %s,
                        expires_at = %s,
                        updated_at = NOW()
                    WHERE user_id = %s
                      AND provider = %s
                """, (new_access_token, new_refresh_token,
                      new_expires_at, user_id, provider))
            else:
                cur.execute("""
                    UPDATE user_integrations
                    SET access_token = %s,
                        expires_at = %s,
                        updated_at = NOW()
                    WHERE user_id = %s
                      AND provider = %s
                """, (new_access_token, new_expires_at,
                      user_id, provider))
            conn.commit()
        log.info(f"Saved refreshed token for {provider}")
    finally:
        conn.close()


def refresh_token_if_needed(tokens: dict, provider: str) -> dict:
    """Refresh OAuth token if within 5 minutes of expiry.
    
    Deprecated: Auto-refresh is now handled in get_integration_tokens.
    """
    return tokens