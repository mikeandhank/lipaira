"""
Google OAuth integration for Lipaira.
Add to gateway: from google_oauth import create_google_routes
"""
import os
import secrets
import redis
from flask import Blueprint, request, redirect, jsonify, g
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
import requests

# Configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'https://lipaira.ai/api/auth/google/callback')

GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com.auth/gmail.readonly',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/contacts.readonly',
]

# Redis client
redis_client = redis.Redis(
    host=os.environ.get('REDIS_HOST', 'redis'),
    port=int(os.environ.get('REDIS_PORT', 6379)),
    password=os.environ.get('REDIS_PASSWORD') or None,
    decode_responses=True
)

google_bp = Blueprint('google', __name__)


def get_flow():
    """Create OAuth flow."""
    config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uris": [GOOGLE_REDIRECT_URI],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    }
    flow = Flow.from_client_config(config, scopes=GOOGLE_SCOPES)
    flow.redirect_uri = GOOGLE_REDIRECT_URI
    return flow


# ── Redis state helpers ──────────────────────────────────────────────────────

def store_oauth_state(state: str, user_id: str, ttl: int = 600):
    """Store state → user_id mapping for 10 minutes."""
    redis_client.setex(f"oauth_state:{state}", ttl, user_id)


def get_oauth_state(state: str) -> str:
    """Retrieve and delete state (one-time use)."""
    user_id = redis_client.get(f"oauth_state:{state}")
    redis_client.delete(f"oauth_state:{state}")
    return user_id if user_id else None


# ── DB helpers ───────────────────────────────────────────────────────────────

def get_db_connection():
    import psycopg2
    from psycopg2.extras import RealDictCursor
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


# ── Routes ───────────────────────────────────────────────────────────────────

@google_bp.route('/api/auth/google/connect')
def google_connect():
    """Start OAuth flow."""
    state = secrets.token_urlsafe(32)
    user_id = request.args.get('user_id', '')
    store_oauth_state(state, user_id)
    
    flow = get_flow()
    auth_url, _ = flow.authorization_url(
        state=state,
        access_type='offline',
        prompt='consent'
    )
    return redirect(auth_url)


@google_bp.route('/api/auth/google/callback')
def google_callback():
    """Handle OAuth callback."""
    state = request.args.get('state')
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return redirect('/dashboard?error=google_denied')

    user_id = get_oauth_state(state)
    if not user_id:
        return redirect('/dashboard?error=invalid_state')

    flow = get_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Get user email
    try:
        user_info = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {creds.token}'}
        ).json()
        email = user_info.get('email', '')
    except:
        email = ''

    save_user_integration(
        user_id=user_id,
        provider='google',
        access_token=creds.token,
        refresh_token=creds.refresh_token,
        expires_at=creds.expiry,
        scopes=' '.join(GOOGLE_SCOPES),
        email=email
    )

    return redirect('/dashboard?connected=google')


@google_bp.route('/api/auth/google/disconnect', methods=['POST'])
def google_disconnect():
    """Disconnect Google account."""
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    delete_user_integration(user_id, 'google')
    return jsonify({'status': 'disconnected'})


@google_bp.route('/api/auth/google/status')
def google_status():
    """Check Google connection status."""
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    integration = get_user_integration(user_id, 'google')
    if not integration:
        return jsonify({'connected': False})
    
    return jsonify({
        'connected': True,
        'email': integration[7] if len(integration) > 7 else ''  # email column
    })


# ── Internal endpoint for agents ───────────────────────────────────────────

@google_bp.route('/api/internal/google-credentials')
def internal_google_credentials():
    """Return Google credentials for agent containers."""
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({'error': 'No user ID'}), 400
    
    integration = get_user_integration(user_id, 'google')
    if not integration:
        return jsonify({'error': 'Google not connected'}), 404
    
    # Build credentials object to refresh if needed
    creds = Credentials(
        token=integration[3],  # access_token
        refresh_token=integration[4],  # refresh_token
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=GOOGLE_SCOPES
    )
    
    # Auto-refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
        save_user_integration(
            user_id=user_id,
            provider='google',
            access_token=creds.token,
            refresh_token=creds.refresh_token,
            expires_at=creds.expiry,
            scopes=' '.join(GOOGLE_SCOPES)
        )
    
    return jsonify({
        'token': creds.token,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'refresh_token': creds.refresh_token,
        'scopes': GOOGLE_SCOPES
    })


def create_google_routes(app):
    """Register routes with Flask app."""
    app.register_blueprint(google_bp)

def create_google_routes(app):
    """Register Google OAuth blueprint with the Flask app."""
    app.register_blueprint(google_bp)
