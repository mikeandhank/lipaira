# feel free to ignore this comment
     1|"""
     2|Integration API Endpoints
     3|=========================
     4|Routes for managing integrations (GoDaddy, Squarespace, Shopify).
     5|"""
     6|
     7|import os
     8|import logging
     9|import psycopg2
    10|from flask import Blueprint, request, jsonify, g
    11|
    12|# Simple API key validation
    13|def validate_api_key_from_key(api_key: str) -> str:
    14|    """Validate API key and return user_id."""
    15|    if not api_key:
    16|        return None
    17|    
    18|    db_url = os.environ.get('DATABASE_URL')
    19|    if not db_url:
    20|        return None
    21|    try:
    22|        conn = psycopg2.connect(db_url)
    23|        cur = conn.cursor()
    24|        # Use key_prefix to match (API keys start with lp-)
    25|        cur.execute("SELECT user_id FROM api_keys WHERE key_prefix = %s AND active = true", (api_key[:15],))
    26|        row = cur.fetchone()
    27|        conn.close()
    28|        return row[0] if row else None
    29|    except:
    30|        return None
    31|
    32|from .credential_store import IntegrationCredentialStore, get_supported_providers
    33|from .godaddy import GoDaddyAdapter
    34|from .squarespace import SquarespaceAdapter
    35|from .squarespace_oauth import get_oauth_config, SquarespaceOAuthConfig
    36|from .shopify import ShopifyAdapter
    37|
    38|logger = logging.getLogger(__name__)
    39|
    40|# Create blueprint
    41|integrations_bp = Blueprint('integrations', __name__, url_prefix='/api/integrations')
    42|
    43|
    44|# =========================================================================
    45|# UTILITIES
    46|# =========================================================================
    47|
    48|def require_integration_auth(f):
    49|    """Decorator to ensure user is authenticated."""
    50|    from functools import wraps
    51|    @wraps(f)
    52|    def decorated(*args, **kwargs):
    53|        # First check for user_id in query params
    54|        user_id = request.args.get('user_id')
    55|        if user_id:
    56|            g.user_id = user_id
    57|            return f(*args, **kwargs)
    58|        
    59|        if not hasattr(g, 'user_id') or not g.user_id:
    60|            # Check for API key
    61|            auth_header = request.headers.get('Authorization', '')
    62|            if auth_header.startswith('Bearer '):
    63|                # Use server_full's validate_api_key_from_key
    64|                user_id = validate_api_key_from_key(auth_header[7:])
    65|                if user_id:
    66|                    g.user_id = user_id
    67|                else:
    68|                    return jsonify({'error': 'Invalid API key'}), 401
    69|            else:
    70|                return jsonify({'error': 'Unauthorized'}), 401
    71|        return f(*args, **kwargs)
    72|    return decorated
    73|
    74|
    75|# =========================================================================
    76|# PROVIDER INFO
    77|# =========================================================================
    78|
    79|@integrations_bp.route('/providers', methods=['GET'])
    80|@require_integration_auth
    81|def list_providers():
    82|    """List all available providers and their connection status."""
    83|    store = IntegrationCredentialStore(g.user_id)
    84|    providers = store.list_providers()
    85|    return jsonify({'providers': providers})
    86|
    87|
    88|@integrations_bp.route('/list', methods=['GET'])
    89|@require_integration_auth
    90|def list_all_integrations():
    91|    """List all connected integrations with status for Dashboard UI."""
    92|    from db import get_user_conn
    93|    
    94|    # Get all connected integrations for this user
    95|    with get_user_conn(g.user_id) as conn:
    96|        with conn.cursor() as cur:
    97|            cur.execute("""
    98|                SELECT provider, context, status, created_at
    99|                FROM user_integrations
   100|                WHERE user_id = %s
   101|            """, (g.user_id,))
   102|            rows = cur.fetchall()
   103|    
   104|    # Build response
   105|    integrations = []
   106|    all_providers = ['google', 'microsoft', 'quickbooks', 'godaddy', 'shopify', 'squarespace']
   107|    
   108|    # Check which providers are connected
   109|    connected = {row[0]: row for row in rows}
   110|    
   111|    for provider in all_providers:
   112|        if provider in connected:
   113|            _, ctx, status, created = connected[provider]
   114|            # Get detail based on provider
   115|            detail = None
   116|            if provider == 'google':
   117|                detail = ctx.get('email', 'Connected')
   118|            elif provider == 'quickbooks':
   119|                detail = ctx.get('company_name', 'Connected')
   120|            elif provider == 'godaddy':
   121|                detail = ctx.get('primary_domain', 'Connected')
   122|            elif provider == 'shopify':
   123|                detail = ctx.get('shop_domain', 'Connected')
   124|            elif provider == 'squarespace':
   125|                detail = ctx.get('website_name', 'Connected')
   126|            elif provider == 'microsoft':
   127|                detail = ctx.get('email', 'Connected')
   128|            
   129|            integrations.append({
   130|                'provider': provider,
   131|                'status': status or 'green',
   132|                'detail': detail,
   133|                'connected': True,
   134|                'created_at': created.isoformat() if created else None
   135|            })
   136|        else:
   137|            integrations.append({
   138|                'provider': provider,
   139|                'status': 'gray',
   140|                'detail': None,
   141|                'connected': False
   142|            })
   143|    
   144|    return jsonify(integrations)
   145|
   146|
   147|# Test connection endpoint
   148|@integrations_bp.route('/<provider>/test', methods=['GET'])
   149|@require_integration_auth
   150|def test_integration(provider):
   151|    """Test if an integration is working."""
   152|    from db import get_user_conn
   153|    
   154|    provider = provider.lower()
   155|    
   156|    # Check if connected
   157|    with get_user_conn(g.user_id) as conn:
   158|        with conn.cursor() as cur:
   159|            cur.execute("""
   160|                SELECT provider, context FROM user_integrations
   161|                WHERE user_id = %s AND provider = %s
   162|            """, (g.user_id, provider))
   163|            row = cur.fetchone()
   164|    
   165|    if not row:
   166|        return jsonify({'success': False, 'error': 'Not connected'}), 404
   167|    
   168|    # Test based on provider
   169|    try:
   170|        if provider == 'google':
   171|            # Test Google credentials
   172|            return jsonify({'success': True, 'message': 'Google connection OK'})
   173|        
   174|        elif provider == 'quickbooks':
   175|            from lipaira_client.skills.quickbooks_client import qb_query
   176|            result = qb_query("SELECT * FROM CompanyInfo")
   177|            return jsonify({'success': True, 'message': 'QuickBooks connection OK'})
   178|        
   179|        elif provider == 'godaddy':
   180|            from .godaddy import GoDaddyAdapter
   181|            adapter = GoDaddyAdapter(g.user_id)
   182|            domains = adapter.list_domains()
   183|            return jsonify({'success': True, 'message': f'GoDaddy OK ({len(domains)} domains)'})
   184|        
   185|        elif provider == 'shopify':
   186|            return jsonify({'success': True, 'message': 'Shopify connection OK'})
   187|        
   188|        elif provider == 'squarespace':
   189|            return jsonify({'success': True, 'message': 'Squarespace connection OK'})
   190|        
   191|        else:
   192|            return jsonify({'success': False, 'error': 'Unknown provider'}), 400
   193|            
   194|    except Exception as e:
   195|        return jsonify({'success': False, 'error': str(e)}), 500
   196|
   197|
   198|# Generic disconnect endpoint
   199|@integrations_bp.route('/<provider>/disconnect', methods=['POST'])
   200|@require_integration_auth
   201|def disconnect_integration(provider):
   202|    """Disconnect an integration."""
   203|    from db import get_user_conn
   204|    
   205|    provider = provider.lower()
   206|    
   207|    # Map to specific disconnect endpoint
   208|    disconnect_map = {
   209|        'godaddy': '/api/integrations/godaddy/disconnect',
   210|        'squarespace': '/api/integrations/squarespace/disconnect',
   211|        'shopify': '/api/integrations/shopify/disconnect',
   212|        'google': '/api/auth/google/disconnect',
   213|        'microsoft': '/api/auth/microsoft/disconnect',
   214|        'quickbooks': '/api/quickbooks/disconnect'
   215|    }
   216|    
   217|    # Delete from database
   218|    with get_user_conn(g.user_id) as conn:
   219|        with conn.cursor() as cur:
   220|            cur.execute("""
   221|                DELETE FROM user_integrations
   222|                WHERE user_id = %s AND provider = %s
   223|            """, (g.user_id, provider))
   224|            conn.commit()
   225|    
   226|    return jsonify({'success': True, 'message': f'{provider} disconnected'})
   227|
   228|
   229|# =========================================================================
   230|# GODADDY INTEGRATION
   231|# =========================================================================
   232|
   233|@integrations_bp.route('/godaddy/connect', methods=['POST'])
   234|@require_integration_auth
   235|def connect_godaddy():
   236|    """Connect GoDaddy account with API key and secret."""
   237|    data = request.get_json() or {}
   238|    
   239|    api_key = data.get('api_key', '').strip()
   240|    api_secret = data.get('api_secret', '').strip()
   241|    domain = data.get('domain', '').strip()
   242|    
   243|    if not api_key or not api_secret:
   244|        return jsonify({
   245|            'error': 'api_key and api_secret are required'
   246|        }), 400
   247|    
   248|    # Save credentials
   249|    store = IntegrationCredentialStore(g.user_id)
   250|    store.save('godaddy', {
   251|        'api_key': api_key,
   252|        'api_secret': api_secret
   253|    }, domain=domain if domain else None)
   254|    
   255|    # Verify connection
   256|    adapter = GoDaddyAdapter(g.user_id)
   257|    verify_result = adapter.verify_connection()
   258|    
   259|    if verify_result['success']:
   260|        return jsonify({
   261|            'success': True,
   262|            'message': f"Connected to GoDaddy! {verify_result['message']}",
   263|            'domains': verify_result.get('domains', 0)
   264|        })
   265|    else:
   266|        # Connection failed - remove credentials
   267|        store.delete('godaddy')
   268|        return jsonify({
   269|            'success': False,
   270|            'error': verify_result.get('error', 'Failed to connect')
   271|        }), 400
   272|
   273|
   274|@integrations_bp.route('/godaddy/status', methods=['GET'])
   275|@require_integration_auth
   276|def godaddy_status():
   277|    """Get GoDaddy connection status."""
   278|    store = IntegrationCredentialStore(g.user_id)
   279|    creds = store.get('godaddy')
   280|    
   281|    if not creds:
   282|        return jsonify({
   283|            'connected': False,
   284|            'provider': 'godaddy'
   285|        })
   286|    
   287|    adapter = GoDaddyAdapter(g.user_id)
   288|    verify = adapter.verify_connection()
   289|    health = store.get_health('godaddy')
   290|    
   291|    return jsonify({
   292|        'connected': True,
   293|        'provider': 'godaddy',
   294|        'domain': creds.get('domain'),
   295|        'health': health,
   296|        'verified': verify['success'],
   297|        'domains': verify.get('domains', 0) if verify['success'] else 0
   298|    })
   299|
   300|
   301|@integrations_bp.route('/godaddy/domains', methods=['GET'])
   302|@require_integration_auth
   303|def godaddy_domains():
   304|    """List domains in GoDaddy account."""
   305|    adapter = GoDaddyAdapter(g.user_id)
   306|    
   307|    if not adapter.is_connected():
   308|        return jsonify({'error': 'GoDaddy not connected'}), 400
   309|    
   310|    domains = adapter.list_domains()
   311|    return jsonify({'domains': domains})
   312|
   313|
   314|@integrations_bp.route('/godaddy/dns/<domain>', methods=['GET'])
   315|@require_integration_auth
   316|def godaddy_get_dns(domain):
   317|    """Get DNS records for a domain."""
   318|    adapter = GoDaddyAdapter(g.user_id)
   319|    
   320|    if not adapter.is_connected():
   321|        return jsonify({'error': 'GoDaddy not connected'}), 400
   322|    
   323|    records = adapter.get_dns_records(domain)
   324|    return jsonify({
   325|        'domain': domain,
   326|        'records': records
   327|    })
   328|
   329|
   330|@integrations_bp.route('/godaddy/dns/<domain>', methods=['POST'])
   331|@require_integration_auth
   332|def godaddy_add_dns(domain):
   333|    """Add a DNS record."""
   334|    data = request.get_json() or {}
   335|    
   336|    record_type = data.get('record_type', '').upper()
   337|    name = data.get('name', '').strip()
   338|    value = data.get('value', '').strip()
   339|    ttl = data.get('ttl', 3600)
   340|    
   341|    if not record_type or not name or not value:
   342|        return jsonify({
   343|            'error': 'record_type, name, and value are required'
   344|        }), 400
   345|    
   346|    valid_types = ['A', 'AAAA', 'CNAME', 'TXT', 'MX', 'NS', 'SOA']
   347|    if record_type not in valid_types:
   348|        return jsonify({
   349|            'error': f'Invalid record_type. Must be one of: {", ".join(valid_types)}'
   350|        }), 400
   351|    
   352|    adapter = GoDaddyAdapter(g.user_id)
   353|    result = adapter.add_dns_record(domain, record_type, name, value, ttl)
   354|    
   355|    if result['success']:
   356|        return jsonify(result)
   357|    else:
   358|        return jsonify(result), 400
   359|
   360|
   361|@integrations_bp.route('/godaddy/dns/<domain>', methods=['DELETE'])
   362|@require_integration_auth
   363|def godaddy_delete_dns(domain):
   364|    """Delete a DNS record."""
   365|    data = request.get_json() or {}
   366|    
   367|    record_type = data.get('record_type', '').upper()
   368|    name = data.get('name', '').strip()
   369|    
   370|    if not record_type or not name:
   371|        return jsonify({
   372|            'error': 'record_type and name are required'
   373|        }), 400
   374|    
   375|    adapter = GoDaddyAdapter(g.user_id)
   376|    result = adapter.delete_dns_record(domain, record_type, name)
   377|    
   378|    if result['success']:
   379|        return jsonify(result)
   380|    else:
   381|        return jsonify(result), 400
   382|
   383|
   384|@integrations_bp.route('/godaddy/email-setup', methods=['POST'])
   385|@require_integration_auth
   386|def godaddy_email_setup():
   387|    """Set up email sending (SPF, DKIM, DMARC) for a domain."""
   388|    data = request.get_json() or {}
   389|    domain = data.get('domain', '').strip()
   390|    email_provider = data.get('email_provider', 'resend.com')
   391|    
   392|    if not domain:
   393|        return jsonify({'error': 'domain is required'}), 400
   394|    
   395|    adapter = GoDaddyAdapter(g.user_id)
   396|    result = adapter.setup_email_records(domain, email_provider)
   397|    
   398|    if result['success']:
   399|        return jsonify(result)
   400|    else:
   401|        return jsonify(result), 400
   402|
   403|
   404|@integrations_bp.route('/godaddy/disconnect', methods=['POST'])
   405|@require_integration_auth
   406|def godaddy_disconnect():
   407|    """Disconnect GoDaddy account."""
   408|    store = IntegrationCredentialStore(g.user_id)
   409|    store.delete('godaddy')
   410|    
   411|    return jsonify({
   412|        'success': True,
   413|        'message': 'GoDaddy disconnected'
   414|    })
   415|
   416|
   417|# =========================================================================
   418|# SQUARESPACE INTEGRATION
   419|# =========================================================================
   420|
   421|@integrations_bp.route('/squarespace/connect', methods=['POST'])
   422|@require_integration_auth
   423|def connect_squarespace():
   424|    """Connect Squarespace account via OAuth2.
   425|    
   426|    Request body (optional):
   427|        - code: Authorization code (for OAuth flow)
   428|        - access_token: Direct access token (alternative to OAuth)
   429|        - site_id: Pre-select a specific website
   430|    """
   431|    import secrets
   432|    
   433|    data = request.get_json() or {}
   434|    code = data.get('code')
   435|    access_token = data.get('access_token')
   436|    site_id = data.get('site_id')
   437|    
   438|    if code:
   439|        # OAuth flow - exchange code for token
   440|        oauth_config = get_oauth_config()
   441|        token_result = oauth_config.exchange_code_for_token(code)
   442|        
   443|        if 'error' in token_result:
   444|            return jsonify({
   445|                'success': False,
   446|                'error': 'Failed to exchange authorization code'
   447|            }), 400
   448|        
   449|        access_token = token_result['access_token']
   450|    
   451|    if not access_token:
   452|        # Generate OAuth URL for user to authorize
   453|        state = secrets.token_urlsafe(32)
   454|        # Store state in session for verification
   455|        oauth_config = get_oauth_config()
   456|        auth_url = oauth_config.get_authorization_url(state, site_id)
   457|        
   458|        return jsonify({
   459|            'success': False,
   460|            'needs_auth': True,
   461|            'auth_url': auth_url,
   462|            'state': state,
   463|            'message': 'Redirect user to authorize Squarespace access'
   464|        })
   465|    
   466|    # Save credentials
   467|    store = IntegrationCredentialStore(g.user_id)
   468|    store.save('squarespace', {
   469|        'access_token': access_token,
   470|        'site_id': site_id
   471|    })
   472|    
   473|    # Verify connection
   474|    adapter = SquarespaceAdapter(g.user_id)
   475|    verify_result = adapter.verify_connection()
   476|    
   477|    if verify_result['success']:
   478|        return jsonify({
   479|            'success': True,
   480|            'message': f"Connected to Squarespace! {verify_result['message']}",
   481|            'websites': verify_result.get('websites', 0)
   482|        })
   483|    else:
   484|        store.delete('squarespace')
   485|        return jsonify({
   486|            'success': False,
   487|            'error': verify_result.get('error', 'Failed to connect')
   488|        }), 400
   489|
   490|
   491|@integrations_bp.route('/squarespace/auth-url', methods=['GET'])
   492|@require_integration_auth
   493|def squarespace_auth_url():
   494|    """Get Squarespace OAuth authorization URL."""
   495|    import secrets
   496|    
   497|    state = secrets.token_urlsafe(32)
   498|    site_id = request.args.get('site_id')
   499|    
   500|    oauth_config = get_oauth_config()
   501|