"""
Square OAuth integration for Lipaira.
Add to gateway: from square_oauth import create_square_routes
"""
import os
import secrets
import hashlib
import base64
import logging
import redis
import requests
from flask import Blueprint, request, redirect, jsonify

logger = logging.getLogger(__name__)

# Configuration
SQUARE_APPLICATION_ID = os.environ.get('SQUARE_APPLICATION_ID', '')
SQUARE_OAUTH_SECRET = os.environ.get('SQUARE_OAUTH_SECRET', '')
SQUARE_REDIRECT_URI = os.environ.get('SQUARE_REDIRECT_URI', 'https://api.lipaira.ai/api/auth/square/callback')

SQUARE_SCOPES = [
    'ITEMS_READ',
    'MERCHANT_PROFILE_READ',
    'CUSTOMERS_READ',
    'CUSTOMERS_WRITE',
    'INVOICES_READ',
    'INVOICES_WRITE',
    'APPOINTMENTS_READ',
]

# Redis client
redis_client = redis.Redis(
    host=os.environ.get('REDIS_HOST', 'redis'),
    port=int(os.environ.get('REDIS_PORT', 6379)),
    password=os.environ.get('REDIS_PASSWORD') or None,
    decode_responses=True
)

square_bp = Blueprint('square', __name__)


def generate_code_verifier():
    """Generate a random code verifier for PKCE."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode()


def generate_code_challenge(verifier):
    """Generate code challenge from verifier."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()


# ── Redis state helpers ──────────────────────────────────────────────────────

def store_oauth_state(state: str, user_id: str, code_verifier: str = None, ttl: int = 600):
    """Store state → user_id mapping for 10 minutes."""
    if code_verifier:
        redis_client.setex(f"oauth_state:{state}", ttl, f"{user_id}:{code_verifier}")
    else:
        redis_client.setex(f"oauth_state:{state}", ttl, user_id)


def get_oauth_state(state: str) -> tuple:
    """Retrieve and delete state (one-time use). Returns (user_id, code_verifier)."""
    value = redis_client.get(f"oauth_state:{state}")
    redis_client.delete(f"oauth_state:{state}")
    
    if not value:
        return None, None
    
    if ':' in value:
        user_id, code_verifier = value.split(':', 1)
        return user_id, code_verifier
    return value, None


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


# ── Routes ───────────────────────────────────────────────────────────────────

@square_bp.route('/api/auth/square/connect')
def square_connect():
    """Start Square OAuth flow."""
    import hashlib
    import psycopg2
    
    user_id = request.args.get('user_id', '')
    
    if not user_id:
        api_key = request.args.get('key', '') or request.headers.get('Authorization', '').replace('Bearer ', '')
        if api_key:
            try:
                key_hash = hashlib.sha256(api_key.encode()).hexdigest()
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("""
                    SELECT user_id FROM api_keys 
                    WHERE key_hash = %s
                    LIMIT 1
                """, (key_hash,))
                row = cur.fetchone()
                if row:
                    user_id = row[0]
                conn.close()
            except Exception as e:
                print(f"OAuth connect error: {e}")
                pass
    
    if not user_id:
        return jsonify({'error': 'User not identified'}), 400
    
    # Generate PKCE code verifier and challenge
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    
    # Store state with code_verifier
    state = secrets.token_urlsafe(32)
    store_oauth_state(state, str(user_id), code_verifier)
    
    # Build Square OAuth URL
    from urllib.parse import urlencode
    auth_params = {
        'client_id': SQUARE_APPLICATION_ID,
        'response_type': 'code',
        'scope': ' '.join(SQUARE_SCOPES),
        'redirect_uri': SQUARE_REDIRECT_URI,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
        'state': state,
    }
    auth_url = f"https://connect.squareup.com/oauth2/authorize?{urlencode(auth_params)}"
    
    return redirect(auth_url)


@square_bp.route('/api/auth/square/callback')
def square_callback():
    """Handle Square OAuth callback."""
    state = request.args.get('state')
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return redirect('https://lipaira.ai/chat?error=square_denied')

    user_id, code_verifier = get_oauth_state(state)
    if not user_id:
        return redirect('https://lipaira.ai/chat?error=invalid_state')

    # Exchange authorization code for token
    token_url = "https://connect.squareup.com/oauth2/token"
    token_data = {
        'client_id': SQUARE_APPLICATION_ID,
        'client_secret': SQUARE_OAUTH_SECRET,
        'code': code,
        'redirect_uri': SQUARE_REDIRECT_URI,
        'code_verifier': code_verifier,
        'grant_type': 'authorization_code',
    }
    
    try:
        resp = requests.post(token_url, json=token_data, timeout=30)
        token_json = resp.json()
        
        if resp.status_code != 200:
            logger.error(f"Square token exchange failed: {token_json}")
            return redirect('https://lipaira.ai/chat?error=square_token_failed')
        
        access_token = token_json.get('access_token', '')
        refresh_token = token_json.get('refresh_token', '')
        expires_at = token_json.get('expires_at', None)
        
        # Save integration
        save_user_integration(
            user_id=user_id,
            provider='square',
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            scopes=' '.join(SQUARE_SCOPES),
        )
        
    except Exception as e:
        logger.error(f"Square OAuth callback error: {e}")
        return redirect('https://lipaira.ai/chat?error=square_error')

    return redirect('https://lipaira.ai/chat?connected=square')


@square_bp.route('/api/auth/square/disconnect', methods=['POST'])
def square_disconnect():
    """Disconnect Square account."""
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    delete_user_integration(user_id, 'square')
    return jsonify({'status': 'disconnected'})


@square_bp.route('/api/auth/square/status')
def square_status():
    """Check Square connection status."""
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    integration = get_user_integration(user_id, 'square')
    if not integration:
        return jsonify({'connected': False})
    
    return jsonify({
        'connected': True,
        'email': integration[7] if len(integration) > 7 else ''
    })


# ── Internal endpoint for agents ───────────────────────────────────────────

@square_bp.route('/api/internal/square-token')
def internal_square_token():
    """Return Square credentials for agent containers."""
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({'error': 'No user ID'}), 400
    
    integration = get_user_integration(user_id, 'square')
    if not integration:
        return jsonify({'error': 'Square not connected'}), 404
    
    # Extract token from row (supports both tuple and dict-like access)
    def _col(row, name, idx):
        try:
            return row[name]
        except (KeyError, TypeError):
            return row[idx] if len(row) > idx else None
    
    access_token = _col(integration, 'access_token', 3)
    refresh_token = _col(integration, 'refresh_token', 4)
    expires_at = _col(integration, 'expires_at', 5)
    
    return jsonify({
        'token': access_token,
        'refresh_token': refresh_token,
        'expires_at': str(expires_at) if expires_at else None,
        'application_id': SQUARE_APPLICATION_ID,
        'oauth_secret': SQUARE_OAUTH_SECRET,
        'scopes': SQUARE_SCOPES,
        'provider': 'square'
    })