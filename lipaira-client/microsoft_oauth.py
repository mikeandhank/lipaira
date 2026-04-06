"""
Microsoft OAuth integration for Lipaira.
"""
import os
import secrets
import redis
from flask import Blueprint, request, redirect, jsonify
import msal


def get_microsoft_credentials():
    """Load Microsoft credentials from ASM at runtime."""
    try:
        from providers import get_secret
        return get_secret('MICROSOFT_CLIENT_ID') or '', get_secret('MICROSOFT_CLIENT_SECRET') or ''
    except:
        return os.environ.get('MICROSOFT_CLIENT_ID', ''), os.environ.get('MICROSOFT_CLIENT_SECRET', '')


# Configuration - loaded at runtime
MICROSOFT_REDIRECT_URI = os.environ.get('MICROSOFT_REDIRECT_URI', 'https://lipaira.ai/api/auth/microsoft/callback')
MICROSOFT_AUTHORITY = "https://login.microsoftonline.com/common"

MICROSOFT_SCOPES = [
    'Mail.Send',
    'Mail.Read',
    'Calendars.ReadWrite',
    'Files.ReadWrite',
    'Contacts.Read',
    'Notes.ReadWrite',
    'offline_access',
    'User.Read',
]

# Redis client
# For lipaira-redis (no auth), don't use password
# For other Redis instances, use password if provided
_redis_host = os.environ.get('REDIS_HOST', 'lipaira-redis')
_redis_pass = None if _redis_host == 'lipaira-redis' else os.environ.get('REDIS_PASSWORD')

redis_client = redis.Redis(
    host=_redis_host,
    port=int(os.environ.get('REDIS_PORT', 6379)),
    password=_redis_pass,
    decode_responses=True
)

microsoft_bp = Blueprint('microsoft', __name__)


def get_msal_app():
    """Create MSAL application."""
    client_id, client_secret = get_microsoft_credentials()
    return msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=MICROSOFT_AUTHORITY
    )


# ── Redis state helpers ──────────────────────────────────────────────────────

def store_oauth_state(state: str, user_id: str, ttl: int = 600):
    redis_client.setex(f"oauth_state:{state}", ttl, user_id)


def get_oauth_state(state: str) -> str:
    user_id = redis_client.get(f"oauth_state:{state}")
    redis_client.delete(f"oauth_state:{state}")
    return user_id if user_id else None


# ── DB helpers ───────────────────────────────────────────────────────────────

def get_db_connection():
    import psycopg2
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise RuntimeError('DATABASE_URL environment variable is required')
    return psycopg2.connect(db_url)


def save_user_integration(user_id, provider, access_token, refresh_token=None, 
                          expires_at=None, scopes=None, email=None):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_integrations
                (user_id, provider, access_token, refresh_token,
                 expires_at, scopes, email, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (user_id, provider) DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = COALESCE(EXCLUDED.refresh_token, user_integrations.refresh_token),
                expires_at = EXCLUDED.expires_at,
                scopes = EXCLUDED.scopes,
                email = EXCLUDED.email,
                updated_at = NOW()
            """, (user_id, provider, access_token, refresh_token,
                  expires_at, scopes, email))
            conn.commit()


def get_user_integration(user_id, provider):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM user_integrations
                WHERE user_id = %s AND provider = %s
            """, (user_id, provider))
            return cur.fetchone()


def delete_user_integration(user_id, provider):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM user_integrations
                WHERE user_id = %s AND provider = %s
            """, (user_id, provider))
            conn.commit()


def update_user_integration(user_id, provider, **kwargs):
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


# ── Routes ───────────────────────────────────────────────────────────────────

@microsoft_bp.route('/api/auth/microsoft/connect')
def microsoft_connect():
    """Start OAuth flow."""
    state = secrets.token_urlsafe(32)
    user_id = request.args.get('user_id', '')
    store_oauth_state(state, user_id)
    
    msal_app = get_msal_app()
    # Use .default scope for static consent
    scopes = ['https://graph.microsoft.com/.default']
    auth_url = msal_app.get_authorization_request_url(
        scopes=scopes,
        state=state,
        redirect_uri=MICROSOFT_REDIRECT_URI
    )
    return redirect(auth_url)


@microsoft_bp.route('/api/auth/microsoft/callback')
def microsoft_callback():
    """Handle OAuth callback."""
    state = request.args.get('state')
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return redirect('/dashboard?error=microsoft_denied')

    user_id = get_oauth_state(state)
    if not user_id:
        return redirect('/dashboard?error=invalid_state')

    msal_app = get_msal_app()
    result = msal_app.acquire_token_by_authorization_code(
        code=code,
        scopes=['https://graph.microsoft.com/.default'],
        redirect_uri=MICROSOFT_REDIRECT_URI
    )

    if 'error' in result:
        return redirect(f"/dashboard?error={result.get('error_description', 'token_error')}")

    # Get user email
    import requests as req
    try:
        user_info = req.get(
            'https://graph.microsoft.com/v1.0/me',
            headers={'Authorization': f"Bearer {result['access_token']}"}
        ).json()
        email = user_info.get('mail') or user_info.get('userPrincipalName')
    except:
        email = ''

    # Calculate expiry
    from datetime import datetime, timedelta
    expires_at = datetime.utcnow() + timedelta(seconds=result.get('expires_in', 3600))

    save_user_integration(
        user_id=user_id,
        provider='microsoft',
        access_token=result['access_token'],
        refresh_token=result.get('refresh_token'),
        expires_at=expires_at,
        scopes=' '.join(MICROSOFT_SCOPES),
        email=email
    )

    return redirect('/dashboard?connected=microsoft')


@microsoft_bp.route('/api/auth/microsoft/disconnect', methods=['POST'])
def microsoft_disconnect():
    """Disconnect Microsoft account."""
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    delete_user_integration(user_id, 'microsoft')
    return jsonify({'status': 'disconnected'})


@microsoft_bp.route('/api/auth/microsoft/status')
def microsoft_status():
    """Check Microsoft connection status."""
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    integration = get_user_integration(user_id, 'microsoft')
    if not integration:
        return jsonify({'connected': False})
    
    return jsonify({
        'connected': True,
        'email': integration[7] if len(integration) > 7 else ''
    })


# ── Internal endpoint for agents ───────────────────────────────────────────

@microsoft_bp.route('/api/internal/microsoft-credentials')
def internal_microsoft_credentials():
    """Return Microsoft access token for agent containers."""
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({'error': 'No user ID'}), 400
    
    integration = get_user_integration(user_id, 'microsoft')
    if not integration:
        return jsonify({'error': 'Microsoft not connected'}), 404
    
    msal_app = get_msal_app()
    accounts = msal_app.get_accounts()
    result = None
    
    # Try silent token acquisition
    if accounts:
        result = msal_app.acquire_token_silent(
            scopes=['https://graph.microsoft.com/.default'],
            account=accounts[0]
        )
    
    # Fall back to refresh token
    if not result or 'error' in (result or {}):
        if integration[4]:  # refresh_token
            result = msal_app.acquire_token_by_refresh_token(
                refresh_token=integration[4],
                scopes=['https://graph.microsoft.com/.default']
            )
    
    if not result or 'access_token' not in result:
        return jsonify({'error': 'Could not refresh Microsoft token'}), 401
    
    # Update stored token if refreshed
    from datetime import datetime, timedelta
    update_user_integration(
        user_id=user_id,
        provider='microsoft',
        access_token=result['access_token'],
        expires_at=datetime.utcnow() + timedelta(seconds=result.get('expires_in', 3600))
    )
    
    return jsonify({'access_token': result['access_token']})


def create_microsoft_routes(app):
    """Register routes with Flask app."""
    app.register_blueprint(microsoft_bp)