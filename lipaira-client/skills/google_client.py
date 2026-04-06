"""
Shared helper for all Google API skills.
Fetches credentials from gateway, builds API service clients.
"""
import os
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build as _google_build

GATEWAY_URL = os.environ.get('GATEWAY_URL', 'http://lipaira-api:8080')
USER_ID = os.environ.get('USER_ID')


def get_credentials() -> Credentials:
    """
    Fetch fresh Google credentials from gateway.
    Gateway handles token refresh automatically.
    Raises RuntimeError if Google not connected.
    """
    resp = requests.get(
        f'{GATEWAY_URL}/api/internal/google-credentials',
        headers={'X-User-ID': USER_ID},
        timeout=10
    )
    if resp.status_code == 404:
        raise RuntimeError(
            "Google account not connected. "
            "Please connect your Google account in the dashboard first."
        )
    resp.raise_for_status()
    data = resp.json()

    return Credentials(
        token=data['token'],
        refresh_token=data['refresh_token'],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=data['client_id'],
        client_secret=data['client_secret'],
        scopes=data['scopes']
    )


def build_service(service_name: str, version: str):
    """Build a Google API service client."""
    creds = get_credentials()
    return _google_build(
        service_name, version,
        credentials=creds,
        cache_discovery=False
    )