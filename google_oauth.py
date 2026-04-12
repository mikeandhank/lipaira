# feel free to ignore this comment
     1|"""
     2|Google OAuth integration for Lipaira.
     3|Add to gateway: from google_oauth import create_google_routes
     4|"""
     5|import os
     6|import secrets
     7|import hashlib
     8|import base64
     9|import logging
    10|import redis
    11|from flask import Blueprint, request, redirect, jsonify, g, session
    12|
    13|logger = logging.getLogger(__name__)
    14|from google_auth_oauthlib.flow import Flow
    15|from google.oauth2.credentials import Credentials
    16|from google.auth.transport.requests import Request as GoogleRequest
    17|import requests
    18|
    19|# Configuration
    20|GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
    21|GOOGLE_CLIENT_SECRET=os.env...ET', '')
    22|GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'https://api.lipaira.ai/api/auth')
    23|
    24|GOOGLE_SCOPES = [
    25|    'https://www.googleapis.com/auth/calendar.events',
    26|    'https://www.googleapis.com/auth/calendar.readonly',
    27|    'https://www.googleapis.com/auth/gmail.send',
    28|    'https://www.googleapis.com/auth/gmail.readonly',
    29|    'https://www.googleapis.com/auth/drive.file',
    30|    'https://www.googleapis.com/auth/contacts.readonly',
    31|    'https://www.googleapis.com/auth/adwords',
    32|]
    33|
    34|# Granular scopes per service
    35|GOOGLE_SERVICE_SCOPES = {
    36|    'gmail': [
    37|        'https://www.googleapis.com/auth/gmail.readonly',
    38|        'https://www.googleapis.com/auth/gmail.send',
    39|    ],
    40|    'google_calendar': [
    41|        'https://www.googleapis.com/auth/calendar.readonly',
    42|        'https://www.googleapis.com/auth/calendar.events',
    43|    ],
    44|    'google_drive': [
    45|        'https://www.googleapis.com/auth/drive.readonly',
    46|        'https://www.googleapis.com/auth/drive.file',
    47|    ],
    48|    'google_business': [
    49|        'https://www.googleapis.com/auth/business.manage',
    50|    ],
    51|}
    52|
    53|# Redis client
    54|redis_client = redis.Redis(
    55|    host=os.environ.get('REDIS_HOST', 'redis'),
    56|    port=int(os.environ.get('REDIS_PORT', 6379)),
    57|    password=os.environ.get('REDIS_PASSWORD') or None,
    58|    decode_responses=True
    59|)
    60|
    61|google_bp = Blueprint('google', __name__)
    62|
    63|
    64|def generate_code_verifier():
    65|    """Generate a random code verifier for PKCE."""
    66|    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode()
    67|
    68|
    69|def generate_code_challenge(verifier):
    70|    """Generate code challenge from verifier."""
    71|    digest = hashlib.sha256(verifier.encode()).digest()
    72|    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
    73|
    74|
    75|def get_flow():
    76|    """Create OAuth flow."""
    77|    config = {
    78|        "web": {
    79|            "client_id": GOOGLE_CLIENT_ID,
    80|            "client_secret": GOOGLE_CLIENT_SECRET,
    81|            "redirect_uris": [GOOGLE_REDIRECT_URI],
    82|            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    83|            "token_uri": "https://oauth2.googleapis.com/token"
    84|        }
    85|    }
    86|    flow = Flow.from_client_config(config, scopes=GOOGLE_SCOPES)
    87|    flow.redirect_uri = GOOGLE_REDIRECT_URI
    88|    return flow
    89|
    90|
    91|# ── Redis state helpers ──────────────────────────────────────────────────────
    92|
    93|def store_oauth_state(state: str, user_id: str, code_verifier: str = None, ttl: int = 600):
    94|    """Store state → user_id mapping for 10 minutes."""
    95|    if code_verifier:
    96|        redis_client.setex(f"oauth_state:{state}", ttl, f"{user_id}:{code_verifier}")
    97|    else:
    98|        redis_client.setex(f"oauth_state:{state}", ttl, user_id)
    99|
   100|
   101|def get_oauth_state(state: str) -> tuple:
   102|    """Retrieve and delete state (one-time use). Returns (user_id, code_verifier)."""
   103|    value = redis_client.get(f"oauth_state:{state}")
   104|    redis_client.delete(f"oauth_state:{state}")
   105|    
   106|    if not value:
   107|        return None, None
   108|    
   109|    # Check if code_verifier is stored (format: "user_id:code_verifier")
   110|    if ':' in value:
   111|        user_id, code_verifier = value.split(':', 1)
   112|        return user_id, code_verifier
   113|    return value, None
   114|
   115|
   116|# ── DB helpers ───────────────────────────────────────────────────────────────
   117|
   118|def get_db_connection():
   119|    import psycopg2
   120|    db_url = os.environ.get('DATABASE_URL')
   121|    if not db_url:
   122|        raise RuntimeError('DATABASE_URL environment variable is required')
   123|    return psycopg2.connect(db_url)
   124|
   125|
   126|def save_user_integration(user_id, provider, access_token, refresh_token=None, 
   127|                          expires_at=None, scopes=None, email=None):
   128|    with get_db_connection() as conn:
   129|        with conn.cursor() as cur:
   130|            cur.execute("""
   131|                INSERT INTO user_integrations
   132|                (user_id, provider, access_token, refresh_token,
   133|                 expires_at, scopes, email, updated_at)
   134|                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
   135|                ON CONFLICT (user_id, provider) DO UPDATE SET
   136|                access_token = EXCLUDED.access_token,
   137|                refresh_token = COALESCE(EXCLUDED.refresh_token, user_integrations.refresh_token),
   138|                expires_at = EXCLUDED.expires_at,
   139|                scopes = EXCLUDED.scopes,
   140|                email = EXCLUDED.email,
   141|                updated_at = NOW()
   142|            """, (user_id, provider, access_token, refresh_token,
   143|                  expires_at, scopes, email))
   144|            conn.commit()
   145|
   146|
   147|def trigger_all_sweeps(user_id: str):
   148|    """
   149|    Run sweeps for all connected integrations for this user.
   150|    Spawns background thread per integration.
   151|    """
   152|    import threading
   153|    
   154|    try:
   155|        conn = get_db_connection()
   156|        cur = conn.cursor()
   157|        cur.execute("""
   158|            SELECT provider FROM user_integrations
   159|            WHERE user_id = %s AND status = 'connected'
   160|        """, (user_id,))
   161|        providers = [row[0] for row in cur.fetchall()]
   162|        cur.close()
   163|        conn.close()
   164|        
   165|        for provider in providers:
   166|            threading.Thread(
   167|                target=trigger_integration_sweep,
   168|                args=(user_id, provider),
   169|                daemon=True
   170|            ).start()
   171|            logger.info(f"Sweep triggered: {user_id}/{provider}")
   172|    
   173|    except Exception as e:
   174|        logger.error(f"trigger_all_sweeps failed: {e}")
   175|
   176|
   177|def trigger_integration_sweep(user_id: str, provider: str):
   178|    """
   179|    Run sweep for a specific integration.
   180|    Extracts data and stores in memory.
   181|    """
   182|    import json
   183|    from datetime import datetime
   184|    
   185|    try:
   186|        integration = get_user_integration(user_id, provider)
   187|        if not integration:
   188|            return
   189|        
   190|        access_token = integration.get('access_token')
   191|        if not access_token:
   192|            return
   193|        
   194|        # Provider-specific sweep logic
   195|        if provider == 'google_calendar':
   196|            sweep_google_calendar(user_id)
   197|        elif provider == 'gmail':
   198|            sweep_gmail(user_id)
   199|        elif provider == 'notion':
   200|            sweep_notion(user_id)
   201|        
   202|        logger.info(f"Sweep completed: {user_id}/{provider}")
   203|    
   204|    except Exception as e:
   205|        logger.error(f"Integration sweep failed: {user_id}/{provider}: {e}")
   206|
   207|
   208|def sweep_google_calendar(user_id: str) -> int:
   209|    """Extract upcoming events and recurring meeting patterns."""
   210|    from skills.base import get_integration_tokens
   211|    from datetime import datetime, timezone, timedelta
   212|    import requests
   213|    count = 0
   214|    
   215|    try:
   216|        tokens = get_integration_tokens(user_id, None, 'google_calendar')
   217|        access_token = tokens['access_token']
   218|        headers = {'Authorization': f'Bearer {access_token}'}
   219|        
   220|        now = datetime.now(timezone.utc).isoformat()
   221|        in_month = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
   222|        
   223|        resp = requests.get(
   224|            'https://www.googleapis.com/calendar/v3/calendars/primary/events',
   225|            headers=headers,
   226|            params={'timeMin': now, 'timeMax': in_month, 'singleEvents': True, 'orderBy': 'startTime', 'maxResults': 50}
   227|        )
   228|        
   229|        if resp.ok:
   230|            events = resp.json().get('items', [])
   231|            if events:
   232|                upcoming = [f"{e.get('summary', 'Untitled')} on {e.get('start', {}).get('dateTime', '')[:10]}" for e in events[:5]]
   233|                save_memory_node(user_id, 'fact', f"Upcoming calendar events: {'; '.join(upcoming)}", 0.95, 'google_calendar_sweep')
   234|                count += 1
   235|                
   236|                recurring = [e.get('summary') for e in events if e.get('recurrence') or e.get('recurringEventId')]
   237|                if recurring:
   238|                    save_memory_node(user_id, 'fact', f"Recurring meetings: {', '.join(set(recurring[:5]))}", 0.85, 'google_calendar_sweep')
   239|                    count += 1
   240|    
   241|    except Exception as e:
   242|        logger.warning(f"Calendar sweep failed for {user_id}: {e}")
   243|    
   244|    return count
   245|
   246|
   247|def sweep_gmail(user_id: str) -> int:
   248|    """Extract inbox patterns and top senders from Gmail."""
   249|    from skills.base import get_integration_tokens
   250|    import requests
   251|    count = 0
   252|    
   253|    try:
   254|        tokens = get_integration_tokens(user_id, None, 'gmail')
   255|        access_token = tokens['access_token']
   256|        headers = {'Authorization': f'Bearer {access_token}'}
   257|        
   258|        resp = requests.get('https://gmail.googleapis.com/gmail/v1/users/me/messages', headers=headers, params={'maxResults': 50, 'q': 'is:inbox'})
   259|        
   260|        if resp.ok:
   261|            messages = resp.json().get('messages', [])
   262|            
   263|            senders = {}
   264|            for msg in messages[:20]:
   265|                detail = requests.get(f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg["id"]}', headers=headers, params={'format': 'metadata', 'metadataHeaders': ['From', 'Subject']}).json()
   266|                hdrs = detail.get('payload', {}).get('headers', [])
   267|                from_val = next((h['value'] for h in hdrs if h['name'] == 'From'), None)
   268|                if from_val:
   269|                    senders[from_val] = senders.get(from_val, 0) + 1
   270|            
   271|            if senders:
   272|                top = sorted(senders.items(), key=lambda x: x[1], reverse=True)[:5]
   273|                top_str = ', '.join(f"{s[0]} ({s[1]} emails)" for s in top)
   274|                save_memory_node(user_id, 'fact', f"Top Gmail senders: {top_str}", 0.85, 'gmail_sweep')
   275|                count += 1
   276|            
   277|            save_memory_node(user_id, 'fact', f"Gmail inbox: {len(messages)} recent messages", 0.9, 'gmail_sweep')
   278|            count += 1
   279|    
   280|    except Exception as e:
   281|        logger.warning(f"Gmail sweep failed for {user_id}: {e}")
   282|    
   283|    return count
   284|
   285|
   286|def sweep_notion(user_id: str) -> int:
   287|    """Index all Notion pages and databases."""
   288|    from skills.base import get_integration_tokens
   289|    import requests
   290|    count = 0
   291|    
   292|    try:
   293|        tokens = get_integration_tokens(user_id, None, 'notion')
   294|        headers = {'Authorization': f"Bearer {tokens['access_token']}", 'Notion-Version': '2022-06-28', 'Content-Type': 'application/json'}
   295|        
   296|        resp = requests.post('https://api.notion.com/v1/search', headers=headers, json={'page_size': 50})
   297|        
   298|        if resp.ok:
   299|            results = resp.json().get('results', [])
   300|            pages = [r for r in results if r['object'] == 'page']
   301|            dbs = [r for r in results if r['object'] == 'database']
   302|            
   303|            if pages:
   304|                titles = []
   305|                for p in pages[:10]:
   306|                    props = p.get('properties', {})
   307|                    title_prop = props.get('title', {})
   308|                    title_parts = title_prop.get('title', [])
   309|                    title = title_parts[0].get('plain_text', 'Untitled') if title_parts else 'Untitled'
   310|                    titles.append(title)
   311|                
   312|                save_memory_node(user_id, 'fact', f"Notion pages ({len(pages)} total): {', '.join(titles)}", 0.85, 'notion_sweep')
   313|                count += 1
   314|            
   315|            if dbs:
   316|                db_titles = []
   317|                for d in dbs[:5]:
   318|                    title_arr = d.get('title', [])
   319|                    title = title_arr[0].get('plain_text', 'Untitled') if title_arr else 'Untitled'
   320|                    db_titles.append(title)
   321|                
   322|                save_memory_node(user_id, 'fact', f"Notion databases: {', '.join(db_titles)}", 0.85, 'notion_sweep')
   323|                count += 1
   324|    
   325|    except Exception as e:
   326|        logger.warning(f"Notion sweep failed for {user_id}: {e}")
   327|    
   328|    return count
   329|
   330|
   331|def save_memory_node(user_id: str, node_type: str, content: str, confidence: float, source: str):
   332|    """Save a memory node."""
   333|    import uuid
   334|    from datetime import datetime
   335|    
   336|    try:
   337|        conn = get_db_connection()
   338|        cur = conn.cursor()
   339|        cur.execute("""
   340|            INSERT INTO memory_nodes (id, user_id, node_type, content, confidence, source, created_at)
   341|            VALUES (%s, %s, %s, %s, %s, %s, NOW())
   342|        """, (str(uuid.uuid4()), user_id, node_type, content, confidence, source))
   343|        conn.commit()
   344|        cur.close()
   345|        conn.close()
   346|    except Exception as e:
   347|        logger.error(f"Save memory node failed: {e}")
   348|
   349|
   350|def get_user_integration(user_id, provider):
   351|    with get_db_connection() as conn:
   352|        with conn.cursor() as cur:
   353|            cur.execute("""
   354|                SELECT * FROM user_integrations
   355|                WHERE user_id = %s AND provider = %s
   356|            """, (user_id, provider))
   357|            return cur.fetchone()
   358|
   359|
   360|def delete_user_integration(user_id, provider):
   361|    with get_db_connection() as conn:
   362|        with conn.cursor() as cur:
   363|            cur.execute("""
   364|                DELETE FROM user_integrations
   365|                WHERE user_id = %s AND provider = %s
   366|            """, (user_id, provider))
   367|            conn.commit()
   368|
   369|
   370|# ── Routes ───────────────────────────────────────────────────────────────────
   371|
   372|@google_bp.route('/api/auth/google/connect')
   373|def google_connect():
   374|    """Start OAuth flow."""
   375|    import hashlib
   376|    import psycopg2
   377|    
   378|    # Try to get user_id from query param, or from API key
   379|    user_id = request.args.get('user_id', '')
   380|    
   381|    if not user_id:
   382|        # Try to get user from API key
   383|        api_key = request.args.get('key', '') or request.headers.get('Authorization', '').replace('Bearer ', '')
   384|        if api_key:
   385|            try:
   386|                # Hash the provided API key to match against key_hash
   387|                key_hash = hashlib.sha256(api_key.encode()).hexdigest()
   388|                conn = get_db_connection()
   389|                cur = conn.cursor()
   390|                # Find user by API key hash
   391|                cur.execute("""
   392|                    SELECT user_id FROM api_keys 
   393|                    WHERE key_hash = %s
   394|                    LIMIT 1
   395|                """, (key_hash,))
   396|                row = cur.fetchone()
   397|                if row:
   398|                    user_id = row[0]
   399|                conn.close()
   400|            except Exception as e:
   401|                print(f"OAuth connect error: {e}")
   402|                pass
   403|    
   404|    if not user_id:
   405|        return jsonify({'error': 'User not identified'}), 400
   406|    
   407|    # Generate PKCE code verifier and challenge
   408|    code_verifier = generate_code_verifier()
   409|    code_challenge = generate_code_challenge(code_verifier)
   410|    
   411|    # Store state with code_verifier
   412|    state = secrets.token_urlsafe(32)
   413|    store_oauth_state(state, str(user_id), code_verifier)
   414|    
   415|    # Create flow with PKCE
   416|    flow = get_flow()
   417|    
   418|    # Use the code_challenge in authorization_url
   419|    from urllib.parse import urlencode
   420|    auth_params = {
   421|        'state': state,
   422|        'access_type': 'offline',
   423|        'prompt': 'consent',
   424|        'code_challenge': code_challenge,
   425|        'code_challenge_method': 'S256'
   426|    }
   427|    auth_url = f"https://accounts.google.com/o/oauth2/auth?{urlencode(auth_params)}"
   428|    
   429|    # Also add client_id and redirect_uri manually since we're not using flow.authorization_url
   430|    auth_url += f"&client_id={GOOGLE_CLIENT_ID}&redirect_uri={GOOGLE_REDIRECT_URI}&response_type=code"
   431|    
   432|    # Add scopes
   433|    auth_url += "&scope=" + "+".join(GOOGLE_SCOPES)
   434|    
   435|    return redirect(auth_url)
   436|
   437|
   438|@google_bp.route('/api/auth/google/callback')
   439|def google_callback():
   440|    """Handle OAuth callback."""
   441|    state = request.args.get('state')
   442|    code = request.args.get('code')
   443|    error = request.args.get('error')
   444|
   445|    if error:
   446|        return redirect('https://lipaira.ai/chat?error=google_denied')
   447|
   448|    user_id, code_verifier = get_oauth_state(state)
   449|    if not user_id:
   450|        return redirect('https://lipaira.ai/chat?error=invalid_state')
   451|
   452|    flow = get_flow()
   453|    
   454|    # Use the code_verifier when fetching token
   455|    if code_verifier:
   456|        flow.fetch_token(
   457|            code=code,
   458|            code_verifier=code_verifier
   459|        )
   460|    else:
   461|        flow.fetch_token(code=code)
   462|    
   463|    creds = flow.credentials
   464|
   465|    # Get user email
   466|    try:
   467|        user_info = requests.get(
   468|            'https://www.googleapis.com/oauth2/v2/userinfo',
   469|            headers={'Authorization': f'Bearer {creds.token}'}
   470|        ).json()
   471|        email = user_info.get('email', '')
   472|    except:
   473|        email = ''
   474|
   475|    save_user_integration(
   476|        user_id=user_id,
   477|        provider='google',
   478|        access_token=creds.token,
   479|        refresh_token=creds.refresh_token,
   480|        expires_at=creds.expiry,
   481|        scopes=' '.join(GOOGLE_SCOPES),
   482|        email=email
   483|    )
   484|
   485|    return redirect('https://lipaira.ai/chat?connected=google')
   486|
   487|
   488|@google_bp.route('/api/auth/google/disconnect', methods=['POST'])
   489|def google_disconnect():
   490|    """Disconnect Google account."""
   491|    user_id = request.headers.get('X-User-ID')
   492|    if not user_id:
   493|        return jsonify({'error': 'Unauthorized'}), 401
   494|    
   495|    delete_user_integration(user_id, 'google')
   496|    return jsonify({'status': 'disconnected'})
   497|
   498|
   499|@google_bp.route('/api/auth/google/status')
   500|def google_status():
   501|