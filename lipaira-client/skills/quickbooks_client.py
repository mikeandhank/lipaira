"""
Shared HTTP client helpers for all QuickBooks skills.
Provides qb_get, qb_post, and qb_query functions that route through
GATEWAY_URL's /api/internal/quickbooks-credentials endpoint to obtain
fresh OAuth tokens on each request, avoiding token refresh complexity.
"""
import os
import requests

GATEWAY_URL = os.environ.get('GATEWAY_URL', 'http://lipaira-api:8080')
USER_ID = os.environ.get('USER_ID')


def get_qb_credentials() -> dict:
    resp = requests.get(
        f'{GATEWAY_URL}/api/internal/quickbooks-credentials',
        headers={'X-User-ID': USER_ID},
        timeout=10
    )
    if resp.status_code == 404:
        raise RuntimeError(
            "QuickBooks not connected. "
            "Please connect QuickBooks in the dashboard first."
        )
    resp.raise_for_status()
    return resp.json()


def qb_get(endpoint: str, params: dict = None) -> dict:
    creds = get_qb_credentials()
    resp = requests.get(
        f"{creds['base_url']}/v3/company/{creds['realm_id']}{endpoint}",
        headers={'Authorization': f"Bearer {creds['access_token']}", 'Accept': 'application/json'},
        params={**(params or {}), 'minorversion': '65'},
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def qb_post(endpoint: str, body: dict) -> dict:
    creds = get_qb_credentials()
    resp = requests.post(
        f"{creds['base_url']}/v3/company/{creds['realm_id']}{endpoint}",
        headers={
            'Authorization': f"Bearer {creds['access_token']}",
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        },
        json=body,
        params={'minorversion': '65'},
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def qb_query(sql: str) -> list:
    creds = get_qb_credentials()
    resp = requests.get(
        f"{creds['base_url']}/v3/company/{creds['realm_id']}/query",
        headers={'Authorization': f"Bearer {creds['access_token']}", 'Accept': 'application/json'},
        params={'query': sql, 'minorversion': '65'},
        timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    query_resp = data.get('QueryResponse', {})
    for key, value in query_resp.items():
        if isinstance(value, list):
            return value
    return []