"""
Shared helper for all Microsoft Graph API skills.
Fetches fresh access token from gateway.
"""
import os
import requests

GATEWAY_URL = os.environ.get('GATEWAY_URL', 'http://lipaira-api:8080')
USER_ID = os.environ.get('USER_ID')
GRAPH_BASE = 'https://graph.microsoft.com/v1.0'


def get_access_token() -> str:
    """
    Fetch fresh Microsoft access token from gateway.
    Raises RuntimeError if Microsoft not connected.
    """
    resp = requests.get(
        f'{GATEWAY_URL}/api/internal/microsoft-credentials',
        headers={'X-User-ID': USER_ID},
        timeout=10
    )
    if resp.status_code == 404:
        raise RuntimeError(
            "Microsoft account not connected. "
            "Please connect your Microsoft account in the dashboard first."
        )
    resp.raise_for_status()
    return resp.json()['access_token']


def graph_get(endpoint: str, params: dict = None) -> dict:
    """GET request to Microsoft Graph API."""
    token = get_access_token()
    resp = requests.get(
        f'{GRAPH_BASE}{endpoint}',
        headers={'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'},
        params=params,
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def graph_post(endpoint: str, body: dict) -> dict:
    """POST request to Microsoft Graph API."""
    token = get_access_token()
    resp = requests.post(
        f'{GRAPH_BASE}{endpoint}',
        headers={'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'},
        json=body,
        timeout=30
    )
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def graph_patch(endpoint: str, body: dict) -> dict:
    """PATCH request to Microsoft Graph API."""
    token = get_access_token()
    resp = requests.patch(
        f'{GRAPH_BASE}{endpoint}',
        headers={'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'},
        json=body,
        timeout=30
    )
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def graph_put_bytes(endpoint: str, data: bytes,
                    content_type: str = 'application/octet-stream') -> dict:
    """PUT binary data to Microsoft Graph API (for file uploads)."""
    token = get_access_token()
    resp = requests.put(
        f'{GRAPH_BASE}{endpoint}',
        headers={'Authorization': f'Bearer {token}',
        'Content-Type': content_type},
        data=data,
        timeout=60
    )
    resp.raise_for_status()
    return resp.json() if resp.content else {}