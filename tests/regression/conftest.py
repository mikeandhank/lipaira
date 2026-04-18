"""
Pytest fixtures for Lipaira regression tests.
"""
import os
import pytest
import requests
import uuid
import time

BASE_URL = os.environ.get('DEPLOYED_API_URL', 'http://localhost:8080')


@pytest.fixture(scope='session')
def api_url():
    """Base API URL from environment."""
    return BASE_URL


@pytest.fixture(scope='session')
def health_check(api_url):
    """Verify API is reachable."""
    try:
        resp = requests.get(f'{api_url}/health', timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.fixture
def test_user(api_url):
    """Create a temporary test user, yield, then delete."""
    email = f'test-{uuid.uuid4().hex[:8]}@lipaira.test'
    password = 'TestPass123!'
    user_id = None

    try:
        # Register
        resp = requests.post(
            f'{api_url}/api/auth/register',
            json={'email': email, 'password': password, 'phone': '+15550000000'},
            timeout=10
        )
        if resp.status_code not in (200, 201):
            pytest.skip(f'Registration failed: {resp.status_code} {resp.text}')

        data = resp.json()
        user_id = data.get('user_id') or data.get('id')
        api_key = data.get('api_key')

        yield {
            'email': email,
            'password': password,
            'user_id': user_id,
            'api_key': api_key,
            'headers': {'Authorization': f'Bearer {api_key}'} if api_key else {}
        }

    finally:
        # Cleanup
        if user_id:
            try:
                requests.delete(
                    f'{api_url}/api/users/{user_id}',
                    headers={'X-Lipaira-Key': api_key} if api_key else {},
                    timeout=5
                )
            except Exception:
                pass


@pytest.fixture
def auth_headers(test_user):
    """Return auth headers from a registered test user."""
    return test_user['headers']
