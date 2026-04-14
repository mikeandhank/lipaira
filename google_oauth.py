"""
Google OAuth integration for Lipaira.
Add to gateway: from google_oauth import create_google_routes
"""
import os
import secrets
import hashlib
import base64
import logging
import redis
from flask import Blueprint, request, redirect, jsonify, g, session

logger = logging.getLogger(__name__)
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
import requests

# Configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'https://api.lipaira.ai/api/auth')

GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/contacts.readonly',
    'https://www.googleapis.com/auth/adwords',
]

# Granular scopes per service
GOOGLE_SERVICE_SCOPES = {
    'gmail': [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.send',
    ],
    'google_calendar': [
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/calendar.events',
    ],
    'google_drive': [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.file',
    ],
    'google_business': [
        'https://www.googleapis.com/auth/business.manage',
    ],
}

# Redis client
redis_client = redis.Redis(
    host=os.environ.get('REDIS_HOST', 'redis'),
    port=int(os.environ.get('REDIS_PORT', 6379)),
    password=os.environ.get('REDIS_PASSWORD') or None,
    decode_responses=True
)

google_bp = Blueprint('google', __name__)


def generate_code_verifier():
    """Generate a random code verifier for PKCE."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode()


def generate_code_challenge(verifier):
    """Generate code challenge from verifier."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()


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
    
    # Check if code_verifier is stored (format: "user_id:code_verifier")
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


def trigger_all_sweeps(user_id: str):
    """
    Run sweeps for all connected integrations for this user.
    Spawns background thread per integration.
    """
    import threading
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT provider FROM user_integrations
            WHERE user_id = %s AND status = 'connected'
        """, (user_id,))
        providers = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        
        for provider in providers:
            threading.Thread(
                target=trigger_integration_sweep,
                args=(user_id, provider),
                daemon=True
            ).start()
            logger.info(f"Sweep triggered: {user_id}/{provider}")
    
    except Exception as e:
        logger.error(f"trigger_all_sweeps failed: {e}")


def trigger_integration_sweep(user_id: str, provider: str):
    """
    Run sweep for a specific integration.
    Extracts data and stores in memory.
    """
    import json
    from datetime import datetime
    
    try:
        integration = get_user_integration(user_id, provider)
        if not integration:
            return
        
        access_token = integration.get('access_token')
        if not access_token:
            return
        
        # Provider-specific sweep logic
        if provider == 'google_calendar':
            sweep_google_calendar(user_id)
        elif provider == 'gmail':
            sweep_gmail(user_id)
        elif provider == 'notion':
            sweep_notion(user_id)
        
        logger.info(f"Sweep completed: {user_id}/{provider}")
    
    except Exception as e:
        logger.error(f"Integration sweep failed: {user_id}/{provider}: {e}")


def sweep_google_calendar(user_id: str) -> int:
    """Extract upcoming events and recurring meeting patterns."""
    from skills.base import get_integration_tokens
    from datetime import datetime, timezone, timedelta
    import requests
    count = 0
    
    try:
        tokens = get_integration_tokens(user_id, None, 'google_calendar')
        access_token = tokens['access_token']
        headers = {'Authorization': f'Bearer {access_token}'}
        
        now = datetime.now(timezone.utc).isoformat()
        in_month = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        
        resp = requests.get(
            'https://www.googleapis.com/calendar/v3/calendars/primary/events',
            headers=headers,
            params={'timeMin': now, 'timeMax': in_month, 'singleEvents': True, 'orderBy': 'startTime', 'maxResults': 50}
        )
        
        if resp.ok:
            events = resp.json().get('items', [])
            if events:
                upcoming = [f"{e.get('summary', 'Untitled')} on {e.get('start', {}).get('dateTime', '')[:10]}" for e in events[:5]]
                save_memory_node(user_id, 'fact', f"Upcoming calendar events: {'; '.join(upcoming)}", 0.95, 'google_calendar_sweep')
                count += 1
                
                recurring = [e.get('summary') for e in events if e.get('recurrence') or e.get('recurringEventId')]
                if recurring:
                    save_memory_node(user_id, 'fact', f"Recurring meetings: {', '.join(set(recurring[:5]))}", 0.85, 'google_calendar_sweep')
                    count += 1
    
    except Exception as e:
        logger.warning(f"Calendar sweep failed for {user_id}: {e}")
    
    return count


def sweep_gmail(user_id: str) -> int:
    """Extract inbox patterns and top senders from Gmail."""
    from skills.base import get_integration_tokens
    import requests
    count = 0
    
    try:
        tokens = get_integration_tokens(user_id, None, 'gmail')
        access_token = tokens['access_token']
        headers = {'Authorization': f'Bearer {access_token}'}
        
        resp = requests.get('https://gmail.googleapis.com/gmail/v1/users/me/messages', headers=headers, params={'maxResults': 50, 'q': 'is:inbox'})
        
        if resp.ok:
            messages = resp.json().get('messages', [])
            
            senders = {}
            for msg in messages[:20]:
                detail = requests.get(f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg["id"]}', headers=headers, params={'format': 'metadata', 'metadataHeaders': ['From', 'Subject']}).json()
                hdrs = detail.get('payload', {}).get('headers', [])
                from_val = next((h['value'] for h in hdrs if h['name'] == 'From'), None)
                if from_val:
                    senders[from_val] = senders.get(from_val, 0) + 1
            
            if senders:
                top = sorted(senders.items(), key=lambda x: x[1], reverse=True)[:5]
                top_str = ', '.join(f"{s[0]} ({s[1]} emails)" for s in top)
                save_memory_node(user_id, 'fact', f"Top Gmail senders: {top_str}", 0.85, 'gmail_sweep')
                count += 1
            
            save_memory_node(user_id, 'fact', f"Gmail inbox: {len(messages)} recent messages", 0.9, 'gmail_sweep')
            count += 1
    
    except Exception as e:
        logger.warning(f"Gmail sweep failed for {user_id}: {e}")
    
    return count


def sweep_notion(user_id: str) -> int:
    """Index all Notion pages and databases."""
    from skills.base import get_integration_tokens
    import requests
    count = 0
    
    try:
        tokens = get_integration_tokens(user_id, None, 'notion')
        headers = {'Authorization': f"Bearer {tokens['access_token']}", 'Notion-Version': '2022-06-28', 'Content-Type': 'application/json'}
        
        resp = requests.post('https://api.notion.com/v1/search', headers=headers, json={'page_size': 50})
        
        if resp.ok:
            results = resp.json().get('results', [])
            pages = [r for r in results if r['object'] == 'page']
            dbs = [r for r in results if r['object'] == 'database']
            
            if pages:
                titles = []
                for p in pages[:10]:
                    props = p.get('properties', {})
                    title_prop = props.get('title', {})
                    title_parts = title_prop.get('title', [])
                    title = title_parts[0].get('plain_text', 'Untitled') if title_parts else 'Untitled'
                    titles.append(title)
                
                save_memory_node(user_id, 'fact', f"Notion pages ({len(pages)} total): {', '.join(titles)}", 0.85, 'notion_sweep')
                count += 1
            
            if dbs:
                db_titles = []
                for d in dbs[:5]:
                    title_arr = d.get('title', [])
                    title = title_arr[0].get('plain_text', 'Untitled') if title_arr else 'Untitled'
                    db_titles.append(title)
                
                save_memory_node(user_id, 'fact', f"Notion databases: {', '.join(db_titles)}", 0.85, 'notion_sweep')
                count += 1
    
    except Exception as e:
        logger.warning(f"Notion sweep failed for {user_id}: {e}")
    
    return count


def save_memory_node(user_id: str, node_type: str, content: str, confidence: float, source: str):
    """Save a memory node."""
    import uuid
    from datetime import datetime
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO memory_nodes (id, user_id, node_type, content, confidence, source, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (str(uuid.uuid4()), user_id, node_type, content, confidence, source))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Save memory node failed: {e}")


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
    import hashlib
    import psycopg2
    
    # Try to get user_id from query param, or from API key
    user_id = request.args.get('user_id', '')
    
    if not user_id:
        # Try to get user from API key
        api_key = request.args.get('key', '') or request.headers.get('Authorization', '').replace('Bearer ', '')
        if api_key:
            try:
                # Hash the provided API key to match against key_hash
                key_hash = hashlib.sha256(api_key.encode()).hexdigest()
                conn = get_db_connection()
                cur = conn.cursor()
                # Find user by API key hash
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
    
    # Create flow with PKCE
    flow = get_flow()
    
    # Use the code_challenge in authorization_url
    from urllib.parse import urlencode
    auth_params = {
        'state': state,
        'access_type': 'offline',
        'prompt': 'consent',
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256'
    }
    auth_url = f"https://accounts.google.com/o/oauth2/auth?{urlencode(auth_params)}"
    
    # Also add client_id and redirect_uri manually since we're not using flow.authorization_url
    auth_url += f"&client_id={GOOGLE_CLIENT_ID}&redirect_uri={GOOGLE_REDIRECT_URI}&response_type=code"
    
    # Add scopes
    auth_url += "&scope=" + "+".join(GOOGLE_SCOPES)
    
    return redirect(auth_url)


@google_bp.route('/api/auth/google/callback')
def google_callback():
    """Handle OAuth callback."""
    state = request.args.get('state')
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return redirect('https://lipaira.ai/chat?error=google_denied')

    user_id, code_verifier = get_oauth_state(state)
    if not user_id:
        return redirect('https://lipaira.ai/chat?error=invalid_state')

    flow = get_flow()
    
    # Use the code_verifier when fetching token
    if code_verifier:
        flow.fetch_token(
            code=code,
            code_verifier=code_verifier
        )
    else:
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

    return redirect('https://lipaira.ai/chat?connected=google')


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
        'email': integration[7] if len(integration) > 7 else ''
    })


# ── Internal endpoint for agents ───────────────────────────────────────────

@google_bp.route('/api/internal/google-credentials')
def internal_google_credentials():
    """Return Google credentials for agent containers.
    Handles both monolithic 'google' and granular provider rows.
    """
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({'error': 'No user ID'}), 400
    
    # Try monolithic google first, then granular providers
    integration = None
    found_provider = None
    for provider in ['google', 'gmail', 'google_calendar', 'google_drive', 'google_business']:
        integration = get_user_integration(user_id, provider)
        if integration:
            found_provider = provider
            break
    
    if not integration:
        return jsonify({'error': 'Google not connected'}), 404
    
    # user_integrations returns a RealDictRow — use column names
    # (falls back to index if not dict)
    def _col(row, name, idx):
        try:
            return row[name]
        except (KeyError, TypeError):
            return row[idx] if len(row) > idx else None
    
    access_token = _col(integration, 'access_token', 3)
    refresh_token = _col(integration, 'refresh_token', 4)
    
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=GOOGLE_SCOPES
    )
    
    # Auto-refresh if expired
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(GoogleRequest())
            save_user_integration(
                user_id=user_id,
                provider=found_provider,
                access_token=creds.token,
                refresh_token=creds.refresh_token,
                expires_at=creds.expiry,
                scopes=' '.join(GOOGLE_SCOPES)
            )
        except Exception as e:
            logger.warning(f"Token refresh failed in internal_google_credentials: {e}")
    
    return jsonify({
        'token': creds.token,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'refresh_token': creds.refresh_token,
        'scopes': GOOGLE_SCOPES,
        'provider': found_provider
    })


# ============= GRANULAR GOOGLE SERVICES =============

@google_bp.route('/api/auth/gmail/connect')
def gmail_connect():
    """Start Gmail OAuth flow."""
    return start_granular_oauth('gmail')


@google_bp.route('/api/auth/gmail/callback')
def gmail_callback():
    """Handle Gmail OAuth callback."""
    return handle_granular_callback('gmail')


@google_bp.route('/api/auth/gmail/status')
def gmail_status():
    """Check Gmail status."""
    return check_granular_status('gmail')


@google_bp.route('/api/auth/gmail/disconnect', methods=['POST'])
def gmail_disconnect():
    """Disconnect Gmail."""
    return disconnect_granular('gmail')


@google_bp.route('/api/auth/google_calendar/connect')
def google_calendar_connect():
    """Start Google Calendar OAuth flow."""
    return start_granular_oauth('google_calendar')


@google_bp.route('/api/auth/google_calendar/callback')
def google_calendar_callback():
    """Handle Google Calendar OAuth callback."""
    return handle_granular_callback('google_calendar')


@google_bp.route('/api/auth/google_calendar/status')
def google_calendar_status():
    """Check Google Calendar status."""
    return check_granular_status('google_calendar')


@google_bp.route('/api/auth/google_calendar/disconnect', methods=['POST'])
def google_calendar_disconnect():
    """Disconnect Google Calendar."""
    return disconnect_granular('google_calendar')


@google_bp.route('/api/auth/google_drive/connect')
def google_drive_connect():
    """Start Google Drive OAuth flow."""
    return start_granular_oauth('google_drive')


@google_bp.route('/api/auth/google_drive/callback')
def google_drive_callback():
    """Handle Google Drive OAuth callback."""
    return handle_granular_callback('google_drive')


@google_bp.route('/api/auth/google_drive/status')
def google_drive_status():
    """Check Google Drive status."""
    return check_granular_status('google_drive')


@google_bp.route('/api/auth/google_drive/disconnect', methods=['POST'])
def google_drive_disconnect():
    """Disconnect Google Drive."""
    return disconnect_granular('google_drive')


@google_bp.route('/api/auth/google_business/connect')
def google_business_connect():
    """Start Google Business OAuth flow."""
    return start_granular_oauth('google_business')


@google_bp.route('/api/auth/google_business/callback')
def google_business_callback():
    """Handle Google Business OAuth callback."""
    return handle_granular_callback('google_business')


@google_bp.route('/api/auth/google_business/status')
def google_business_status():
    """Check Google Business status."""
    return check_granular_status('google_business')


@google_bp.route('/api/auth/google_business/disconnect', methods=['POST'])
def google_business_disconnect():
    """Disconnect Google Business."""
    return disconnect_granular('google_business')


def start_granular_oauth(service):
    """Start OAuth flow for specific service."""
    scopes = GOOGLE_SERVICE_SCOPES.get(service, [])
    if not scopes:
        return jsonify({'error': f'Unknown service: {service}'}), 400
    
    # Get user_id from query param (passed from frontend)
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    
    # Use service-specific redirect URI
    redirect_uri = f'https://api.lipaira.ai/api/auth/{service}/callback'
    
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    
    # Use proper params dict - state goes HERE only, not appended to URL
    from urllib.parse import urlencode
    auth_params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': ' '.join(scopes),
        'access_type': 'offline',
        'prompt': 'consent',
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
        'state': f"{user_id}:{service}"  # Include user_id in state
    }
    auth_url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode(auth_params)
    
    # Store code_verifier in Redis with combined key
    redis_client.setex(f'google_oauth_state:{user_id}:{service}', 300, code_verifier)
    
    return redirect(auth_url)


def handle_granular_callback(service):
    """Handle granular OAuth callback."""
    try:
        # Get user_id and service from the state parameter
        state = request.args.get('state', '')
        if ':' in state:
            user_id, svc = state.split(':', 1)
        else:
            return redirect('https://lipaira.ai/chat?error=invalid_state')
        
        code_verifier = redis_client.get(f'google_oauth_state:{user_id}:{service}')
        if not code_verifier:
            return redirect('https://lipaira.ai/chat?error=oauth_timeout')
        
        scopes = GOOGLE_SERVICE_SCOPES.get(service, [])
        redirect_uri = f'https://api.lipaira.ai/api/auth/{service}/callback'
        
        client_config = {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uris": [redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        }
        
        flow = Flow.from_client_config(client_config, scopes=scopes)
        flow.redirect_uri = redirect_uri
        
        flow.fetch_token(
            code=request.args.get('code'),
            code_verifier=code_verifier
        )
        
        creds = flow.credentials
        
        # Get user info
        try:
            from googleapiclient.discovery import build
            user_creds = Credentials(token=creds.token)
            user_service = build('oauth2', 'v2', credentials=user_creds, cache_discovery=False)
            user_info = user_service.userinfo().get().execute()
            email = user_info.get('email')
        except:
            email = None
        
        # Save to database with service-specific provider
        save_user_integration(user_id, service, creds.token, creds.refresh_token,
                            creds.expiry.isoformat() if creds.expiry else None,
                            ' '.join(scopes), email)
        
        # Trigger memory sweeps after OAuth connect
        trigger_all_sweeps(user_id)
        
        redis_client.delete(f'google_oauth_state:{user_id}:{service}')
        
        return redirect(f'https://lipaira.ai/chat?connected={service}')
        
    except Exception as e:
        logger.error(f"Granular OAuth callback error: {e}")
        return redirect(f'https://lipaira.ai/chat?error=oauth_failed')


def check_granular_status(service):
    """Check granular service status."""
    user_id = request.args.get('user_id') or g.get('user_id') or session.get('user_id')
    if not user_id:
        return jsonify({'connected': False, 'error': 'user_id required'})
    
    integration = get_user_integration(user_id, service)
    
    if not integration:
        return jsonify({'connected': False, 'service': service})
    
    return jsonify({
        'connected': True,
        'service': service,
        'email': integration.get('email'),
        'expires_at': integration.get('expires_at')
    })


def disconnect_granular(service):
    """Disconnect granular service."""
    user_id = request.json.get('user_id') if request.is_json else None
    user_id = user_id or g.get('user_id') or session.get('user_id')
    
    if user_id:
        delete_user_integration(user_id, service)
    
    return jsonify({'status': 'disconnected', 'service': service})


def create_google_routes(app):
    """Register routes with Flask app."""
    app.register_blueprint(google_bp)