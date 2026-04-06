"""
QuickBooks OAuth integration for Lipaira.
"""
import os
import secrets
import redis
from flask import Blueprint, request, redirect, jsonify
import requests as req
from urllib.parse import urlencode
from datetime import datetime, timedelta

# Configuration - Get credentials at runtime, not import time
def get_quickbooks_client_id():
    from providers import get_secret
    return get_secret('QUICKBOOKS_CLIENT_ID') or ''

def get_quickbooks_client_secret():
    from providers import get_secret
    return get_secret('QUICKBOOKS_CLIENT_SECRET') or ''

QUICKBOOKS_REDIRECT_URI = os.environ.get('QUICKBOOKS_REDIRECT_URI', 'https://lipaira.ai/api/auth/quickbooks/callback')

QUICKBOOKS_SCOPES = [
    'com.intuit.quickbooks.accounting',
    'openid',
    'profile',
    'email',
    'phone',
    'address',
]

QUICKBOOKS_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
QUICKBOOKS_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
QUICKBOOKS_REVOKE_URL = "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"

QB_SANDBOX_BASE = "https://sandbox-quickbooks.api.intuit.com"
QB_PROD_BASE = "https://quickbooks.api.intuit.com"

def get_qb_base():
    return QB_SANDBOX_BASE if os.environ.get('QB_SANDBOX', 'true') == 'true' else QB_PROD_BASE

# Redis
redis_client = redis.Redis(
    host=os.environ.get('REDIS_HOST', 'redis'),
    port=int(os.environ.get('REDIS_PORT', 6379)),
    password=os.environ.get('REDIS_PASSWORD') or None,
    decode_responses=True
)

quickbooks_bp = Blueprint('quickbooks', __name__)


def store_oauth_state(state: str, user_id: str, ttl: int = 600):
    redis_client.setex(f"oauth_state:{state}", ttl, user_id)


def get_oauth_state(state: str) -> str:
    user_id = redis_client.get(f"oauth_state:{state}")
    redis_client.delete(f"oauth_state:{state}")
    return user_id if user_id else None


def get_db_connection():
    import psycopg2
    db_url = os.environ.get('DATABASE_URL', 'postgresql://nexusos:ChangeMe123!@postgres:5432/nexusos')
    return psycopg2.connect(db_url)


def save_user_integration(user_id, provider, access_token, refresh_token=None, 
                          expires_at=None, scopes=None, email=None, extra=None):
    import json
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_integrations
                (user_id, provider, access_token, refresh_token,
                 expires_at, scopes, email, extra, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (user_id, provider) DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = COALESCE(EXCLUDED.refresh_token, user_integrations.refresh_token),
                expires_at = EXCLUDED.expires_at,
                scopes = EXCLUDED.scopes,
                email = EXCLUDED.email,
                extra = COALESCE(EXCLUDED.extra, user_integrations.extra),
                updated_at = NOW()
            """, (user_id, provider, access_token, refresh_token,
                  expires_at, scopes, email, json.dumps(extra) if extra else None))
            conn.commit()


def get_user_integration(user_id, provider):
    import json
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM user_integrations
                WHERE user_id = %s AND provider = %s
            """, (user_id, provider))
            row = cur.fetchone()
            if row:
                # Convert to dict with column names
                cols = ['id', 'user_id', 'provider', 'access_token', 'refresh_token',
                        'expires_at', 'scopes', 'email', 'created_at', 'updated_at', 'extra']
                result = dict(zip(cols, row))
                if result.get('extra') and isinstance(result['extra'], str):
                    result['extra'] = json.loads(result['extra'])
                return result
            return None


def update_user_integration(user_id, provider, **kwargs):
    import json
    fields = ', '.join(f"{k} = %s" for k in kwargs)
    values = list(kwargs.values()) + [user_id, provider]
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                UPDATE user_integrations
                SET {fields}, updated_at = NOW()
                WHERE user_id = %s AND provider = %s
            """, values)
            conn.commit()


def delete_user_integration(user_id, provider):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM user_integrations
                WHERE user_id = %s AND provider = %s
            """, (user_id, provider))
            conn.commit()


# ── Routes ───────────────────────────────────────────────────────────────────

@quickbooks_bp.route('/api/auth/quickbooks/connect')
def quickbooks_connect():
    state = secrets.token_urlsafe(32)
    user_id = request.args.get('user_id', '')
    store_oauth_state(state, user_id)

    params = {
        'client_id': get_quickbooks_client_id(),
        'response_type': 'code',
        'scope': ' '.join(QUICKBOOKS_SCOPES),
        'redirect_uri': QUICKBOOKS_REDIRECT_URI,
        'state': state
    }
    auth_url = f"{QUICKBOOKS_AUTH_URL}?{urlencode(params)}"
    return redirect(auth_url)


@quickbooks_bp.route('/api/auth/quickbooks/callback')
def quickbooks_callback():
    state = request.args.get('state')
    code = request.args.get('code')
    realm_id = request.args.get('realmId')
    error = request.args.get('error')

    if error:
        return redirect('/dashboard?error=quickbooks_denied')

    user_id = get_oauth_state(state)
    if not user_id:
        return redirect('/dashboard?error=invalid_state')

    # Exchange code for tokens
    import base64
    credentials = base64.b64encode(
        f"{get_quickbooks_client_id()}:{get_quickbooks_client_secret()}".encode()
    ).decode()

    token_resp = req.post(
        QUICKBOOKS_TOKEN_URL,
        headers={
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': QUICKBOOKS_REDIRECT_URI
        }
    )
    token_resp.raise_for_status()
    tokens = token_resp.json()

    expires_at = datetime.utcnow() + timedelta(seconds=tokens.get('expires_in', 3600))

    # Get company name
    company_info = req.get(
        f"{get_qb_base()}/v3/company/{realm_id}/companyinfo/{realm_id}",
        headers={'Authorization': f"Bearer {tokens['access_token']}", 'Accept': 'application/json'}
    ).json()
    company_name = company_info.get('CompanyInfo', {}).get('CompanyName', 'Your Company')

    save_user_integration(
        user_id=user_id,
        provider='quickbooks',
        access_token=tokens['access_token'],
        refresh_token=tokens.get('refresh_token'),
        expires_at=expires_at,
        scopes=' '.join(QUICKBOOKS_SCOPES),
        email=company_name,
        extra={'realm_id': realm_id}
    )

    return redirect('/dashboard?connected=quickbooks')


@quickbooks_bp.route('/api/auth/quickbooks/disconnect', methods=['POST'])
def quickbooks_disconnect():
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    integration = get_user_integration(user_id, 'quickbooks')
    if integration and integration.get('refresh_token'):
        import base64
        credentials = base64.b64encode(
            f"{get_quickbooks_client_id()}:{get_quickbooks_client_secret()}".encode()
        ).decode()
        try:
            req.post(
                QUICKBOOKS_REVOKE_URL,
                headers={'Authorization': f'Basic {credentials}', 'Content-Type': 'application/json'},
                json={'token': integration['refresh_token']}
            )
        except:
            pass
    
    delete_user_integration(user_id, 'quickbooks')
    return jsonify({'status': 'disconnected'})


@quickbooks_bp.route('/api/auth/quickbooks/status')
def quickbooks_status():
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    integration = get_user_integration(user_id, 'quickbooks')
    if not integration:
        return jsonify({'connected': False})
    
    return jsonify({
        'connected': True,
        'company_name': integration.get('email')
    })


@quickbooks_bp.route('/api/internal/quickbooks-credentials')
def internal_quickbooks_credentials():
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({'error': 'No user ID'}), 400
    
    integration = get_user_integration(user_id, 'quickbooks')
    if not integration:
        return jsonify({'error': 'QuickBooks not connected'}), 404

    needs_refresh = (
        not integration.get('expires_at') or
        integration['expires_at'] < datetime.utcnow() + timedelta(minutes=5)
    )

    if needs_refresh and integration.get('refresh_token'):
        import base64
        credentials = base64.b64encode(
            f"{get_quickbooks_client_id()}:{get_quickbooks_client_secret()}".encode()
        ).decode()

        token_resp = req.post(
            QUICKBOOKS_TOKEN_URL,
            headers={'Authorization': f'Basic {credentials}', 'Content-Type': 'application/x-www-form-urlencoded'},
            data={'grant_type': 'refresh_token', 'refresh_token': integration['refresh_token']}
        )

        if token_resp.ok:
            tokens = token_resp.json()
            update_user_integration(
                user_id=user_id,
                provider='quickbooks',
                access_token=tokens['access_token'],
                expires_at=datetime.utcnow() + timedelta(seconds=tokens.get('expires_in', 3600))
            )
            integration['access_token'] = tokens['access_token']

    extra = integration.get('extra') or {}
    realm_id = extra.get('realm_id') if isinstance(extra, dict) else ''

    return jsonify({
        'access_token': integration['access_token'],
        'realm_id': realm_id,
        'base_url': get_qb_base()
    })


def create_quickbooks_routes(app):
    app.register_blueprint(quickbooks_bp)