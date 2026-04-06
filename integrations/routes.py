"""
Integration API Endpoints
=========================
Routes for managing integrations (GoDaddy, Squarespace, Shopify).
"""

import os
import logging
import psycopg2
from flask import Blueprint, request, jsonify, g

# Simple API key validation
def validate_api_key_from_key(api_key: str) -> str:
    """Validate API key and return user_id."""
    if not api_key:
        return None
    
    db_url = os.environ.get('DATABASE_URL', 'postgresql://nexusos:ChangeMe123!@postgres:5432/nexusos')
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        # Use key_prefix to match (API keys start with lp-)
        cur.execute("SELECT user_id FROM api_keys WHERE key_prefix = %s AND active = true", (api_key[:15],))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except:
        return None

from .credential_store import IntegrationCredentialStore, get_supported_providers
from .godaddy import GoDaddyAdapter
from .squarespace import SquarespaceAdapter
from .squarespace_oauth import get_oauth_config, SquarespaceOAuthConfig
from .shopify import ShopifyAdapter

logger = logging.getLogger(__name__)

# Create blueprint
integrations_bp = Blueprint('integrations', __name__, url_prefix='/api/integrations')


# =========================================================================
# UTILITIES
# =========================================================================

def require_integration_auth(f):
    """Decorator to ensure user is authenticated."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        # First check for user_id in query params
        user_id = request.args.get('user_id')
        if user_id:
            g.user_id = user_id
            return f(*args, **kwargs)
        
        if not hasattr(g, 'user_id') or not g.user_id:
            # Check for API key
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                # Use server_full's validate_api_key_from_key
                user_id = validate_api_key_from_key(auth_header[7:])
                if user_id:
                    g.user_id = user_id
                else:
                    return jsonify({'error': 'Invalid API key'}), 401
            else:
                return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


# =========================================================================
# PROVIDER INFO
# =========================================================================

@integrations_bp.route('/providers', methods=['GET'])
@require_integration_auth
def list_providers():
    """List all available providers and their connection status."""
    store = IntegrationCredentialStore(g.user_id)
    providers = store.list_providers()
    return jsonify({'providers': providers})


@integrations_bp.route('/list', methods=['GET'])
@require_integration_auth
def list_all_integrations():
    """List all connected integrations with status for Dashboard UI."""
    from db import get_user_conn
    
    # Get all connected integrations for this user
    with get_user_conn(g.user_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT provider, context, status, created_at
                FROM user_integrations
                WHERE user_id = %s
            """, (g.user_id,))
            rows = cur.fetchall()
    
    # Build response
    integrations = []
    all_providers = ['google', 'microsoft', 'quickbooks', 'godaddy', 'shopify', 'squarespace']
    
    # Check which providers are connected
    connected = {row[0]: row for row in rows}
    
    for provider in all_providers:
        if provider in connected:
            _, ctx, status, created = connected[provider]
            # Get detail based on provider
            detail = None
            if provider == 'google':
                detail = ctx.get('email', 'Connected')
            elif provider == 'quickbooks':
                detail = ctx.get('company_name', 'Connected')
            elif provider == 'godaddy':
                detail = ctx.get('primary_domain', 'Connected')
            elif provider == 'shopify':
                detail = ctx.get('shop_domain', 'Connected')
            elif provider == 'squarespace':
                detail = ctx.get('website_name', 'Connected')
            elif provider == 'microsoft':
                detail = ctx.get('email', 'Connected')
            
            integrations.append({
                'provider': provider,
                'status': status or 'green',
                'detail': detail,
                'connected': True,
                'created_at': created.isoformat() if created else None
            })
        else:
            integrations.append({
                'provider': provider,
                'status': 'gray',
                'detail': None,
                'connected': False
            })
    
    return jsonify(integrations)


# Test connection endpoint
@integrations_bp.route('/<provider>/test', methods=['GET'])
@require_integration_auth
def test_integration(provider):
    """Test if an integration is working."""
    from db import get_user_conn
    
    provider = provider.lower()
    
    # Check if connected
    with get_user_conn(g.user_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT provider, context FROM user_integrations
                WHERE user_id = %s AND provider = %s
            """, (g.user_id, provider))
            row = cur.fetchone()
    
    if not row:
        return jsonify({'success': False, 'error': 'Not connected'}), 404
    
    # Test based on provider
    try:
        if provider == 'google':
            # Test Google credentials
            return jsonify({'success': True, 'message': 'Google connection OK'})
        
        elif provider == 'quickbooks':
            from lipaira_client.skills.quickbooks_client import qb_query
            result = qb_query("SELECT * FROM CompanyInfo")
            return jsonify({'success': True, 'message': 'QuickBooks connection OK'})
        
        elif provider == 'godaddy':
            from .godaddy import GoDaddyAdapter
            adapter = GoDaddyAdapter(g.user_id)
            domains = adapter.list_domains()
            return jsonify({'success': True, 'message': f'GoDaddy OK ({len(domains)} domains)'})
        
        elif provider == 'shopify':
            return jsonify({'success': True, 'message': 'Shopify connection OK'})
        
        elif provider == 'squarespace':
            return jsonify({'success': True, 'message': 'Squarespace connection OK'})
        
        else:
            return jsonify({'success': False, 'error': 'Unknown provider'}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Generic disconnect endpoint
@integrations_bp.route('/<provider>/disconnect', methods=['POST'])
@require_integration_auth
def disconnect_integration(provider):
    """Disconnect an integration."""
    from db import get_user_conn
    
    provider = provider.lower()
    
    # Map to specific disconnect endpoint
    disconnect_map = {
        'godaddy': '/api/integrations/godaddy/disconnect',
        'squarespace': '/api/integrations/squarespace/disconnect',
        'shopify': '/api/integrations/shopify/disconnect',
        'google': '/api/auth/google/disconnect',
        'microsoft': '/api/auth/microsoft/disconnect',
        'quickbooks': '/api/quickbooks/disconnect'
    }
    
    # Delete from database
    with get_user_conn(g.user_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM user_integrations
                WHERE user_id = %s AND provider = %s
            """, (g.user_id, provider))
            conn.commit()
    
    return jsonify({'success': True, 'message': f'{provider} disconnected'})


# =========================================================================
# GODADDY INTEGRATION
# =========================================================================

@integrations_bp.route('/godaddy/connect', methods=['POST'])
@require_integration_auth
def connect_godaddy():
    """Connect GoDaddy account with API key and secret."""
    data = request.get_json() or {}
    
    api_key = data.get('api_key', '').strip()
    api_secret = data.get('api_secret', '').strip()
    domain = data.get('domain', '').strip()
    
    if not api_key or not api_secret:
        return jsonify({
            'error': 'api_key and api_secret are required'
        }), 400
    
    # Save credentials
    store = IntegrationCredentialStore(g.user_id)
    store.save('godaddy', {
        'api_key': api_key,
        'api_secret': api_secret
    }, domain=domain if domain else None)
    
    # Verify connection
    adapter = GoDaddyAdapter(g.user_id)
    verify_result = adapter.verify_connection()
    
    if verify_result['success']:
        return jsonify({
            'success': True,
            'message': f"Connected to GoDaddy! {verify_result['message']}",
            'domains': verify_result.get('domains', 0)
        })
    else:
        # Connection failed - remove credentials
        store.delete('godaddy')
        return jsonify({
            'success': False,
            'error': verify_result.get('error', 'Failed to connect')
        }), 400


@integrations_bp.route('/godaddy/status', methods=['GET'])
@require_integration_auth
def godaddy_status():
    """Get GoDaddy connection status."""
    store = IntegrationCredentialStore(g.user_id)
    creds = store.get('godaddy')
    
    if not creds:
        return jsonify({
            'connected': False,
            'provider': 'godaddy'
        })
    
    adapter = GoDaddyAdapter(g.user_id)
    verify = adapter.verify_connection()
    health = store.get_health('godaddy')
    
    return jsonify({
        'connected': True,
        'provider': 'godaddy',
        'domain': creds.get('domain'),
        'health': health,
        'verified': verify['success'],
        'domains': verify.get('domains', 0) if verify['success'] else 0
    })


@integrations_bp.route('/godaddy/domains', methods=['GET'])
@require_integration_auth
def godaddy_domains():
    """List domains in GoDaddy account."""
    adapter = GoDaddyAdapter(g.user_id)
    
    if not adapter.is_connected():
        return jsonify({'error': 'GoDaddy not connected'}), 400
    
    domains = adapter.list_domains()
    return jsonify({'domains': domains})


@integrations_bp.route('/godaddy/dns/<domain>', methods=['GET'])
@require_integration_auth
def godaddy_get_dns(domain):
    """Get DNS records for a domain."""
    adapter = GoDaddyAdapter(g.user_id)
    
    if not adapter.is_connected():
        return jsonify({'error': 'GoDaddy not connected'}), 400
    
    records = adapter.get_dns_records(domain)
    return jsonify({
        'domain': domain,
        'records': records
    })


@integrations_bp.route('/godaddy/dns/<domain>', methods=['POST'])
@require_integration_auth
def godaddy_add_dns(domain):
    """Add a DNS record."""
    data = request.get_json() or {}
    
    record_type = data.get('record_type', '').upper()
    name = data.get('name', '').strip()
    value = data.get('value', '').strip()
    ttl = data.get('ttl', 3600)
    
    if not record_type or not name or not value:
        return jsonify({
            'error': 'record_type, name, and value are required'
        }), 400
    
    valid_types = ['A', 'AAAA', 'CNAME', 'TXT', 'MX', 'NS', 'SOA']
    if record_type not in valid_types:
        return jsonify({
            'error': f'Invalid record_type. Must be one of: {", ".join(valid_types)}'
        }), 400
    
    adapter = GoDaddyAdapter(g.user_id)
    result = adapter.add_dns_record(domain, record_type, name, value, ttl)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@integrations_bp.route('/godaddy/dns/<domain>', methods=['DELETE'])
@require_integration_auth
def godaddy_delete_dns(domain):
    """Delete a DNS record."""
    data = request.get_json() or {}
    
    record_type = data.get('record_type', '').upper()
    name = data.get('name', '').strip()
    
    if not record_type or not name:
        return jsonify({
            'error': 'record_type and name are required'
        }), 400
    
    adapter = GoDaddyAdapter(g.user_id)
    result = adapter.delete_dns_record(domain, record_type, name)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@integrations_bp.route('/godaddy/email-setup', methods=['POST'])
@require_integration_auth
def godaddy_email_setup():
    """Set up email sending (SPF, DKIM, DMARC) for a domain."""
    data = request.get_json() or {}
    domain = data.get('domain', '').strip()
    email_provider = data.get('email_provider', 'resend.com')
    
    if not domain:
        return jsonify({'error': 'domain is required'}), 400
    
    adapter = GoDaddyAdapter(g.user_id)
    result = adapter.setup_email_records(domain, email_provider)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@integrations_bp.route('/godaddy/disconnect', methods=['POST'])
@require_integration_auth
def godaddy_disconnect():
    """Disconnect GoDaddy account."""
    store = IntegrationCredentialStore(g.user_id)
    store.delete('godaddy')
    
    return jsonify({
        'success': True,
        'message': 'GoDaddy disconnected'
    })


# =========================================================================
# SQUARESPACE INTEGRATION
# =========================================================================

@integrations_bp.route('/squarespace/connect', methods=['POST'])
@require_integration_auth
def connect_squarespace():
    """Connect Squarespace account via OAuth2.
    
    Request body (optional):
        - code: Authorization code (for OAuth flow)
        - access_token: Direct access token (alternative to OAuth)
        - site_id: Pre-select a specific website
    """
    import secrets
    
    data = request.get_json() or {}
    code = data.get('code')
    access_token = data.get('access_token')
    site_id = data.get('site_id')
    
    if code:
        # OAuth flow - exchange code for token
        oauth_config = get_oauth_config()
        token_result = oauth_config.exchange_code_for_token(code)
        
        if 'error' in token_result:
            return jsonify({
                'success': False,
                'error': 'Failed to exchange authorization code'
            }), 400
        
        access_token = token_result['access_token']
    
    if not access_token:
        # Generate OAuth URL for user to authorize
        state = secrets.token_urlsafe(32)
        # Store state in session for verification
        oauth_config = get_oauth_config()
        auth_url = oauth_config.get_authorization_url(state, site_id)
        
        return jsonify({
            'success': False,
            'needs_auth': True,
            'auth_url': auth_url,
            'state': state,
            'message': 'Redirect user to authorize Squarespace access'
        })
    
    # Save credentials
    store = IntegrationCredentialStore(g.user_id)
    store.save('squarespace', {
        'access_token': access_token,
        'site_id': site_id
    })
    
    # Verify connection
    adapter = SquarespaceAdapter(g.user_id)
    verify_result = adapter.verify_connection()
    
    if verify_result['success']:
        return jsonify({
            'success': True,
            'message': f"Connected to Squarespace! {verify_result['message']}",
            'websites': verify_result.get('websites', 0)
        })
    else:
        store.delete('squarespace')
        return jsonify({
            'success': False,
            'error': verify_result.get('error', 'Failed to connect')
        }), 400


@integrations_bp.route('/squarespace/auth-url', methods=['GET'])
@require_integration_auth
def squarespace_auth_url():
    """Get Squarespace OAuth authorization URL."""
    import secrets
    
    state = secrets.token_urlsafe(32)
    site_id = request.args.get('site_id')
    
    oauth_config = get_oauth_config()
    auth_url = oauth_config.get_authorization_url(state, site_id)
    
    return jsonify({
        'auth_url': auth_url,
        'state': state,
        'redirect_uri': oauth_config.redirect_uri
    })


@integrations_bp.route('/squarespace/status', methods=['GET'])
@require_integration_auth
def squarespace_status():
    """Get Squarespace connection status."""
    store = IntegrationCredentialStore(g.user_id)
    creds = store.get('squarespace')
    
    if not creds:
        return jsonify({
            'connected': False,
            'provider': 'squarespace'
        })
    
    adapter = SquarespaceAdapter(g.user_id)
    verify = adapter.verify_connection()
    health = store.get_health('squarespace')
    
    return jsonify({
        'connected': True,
        'provider': 'squarespace',
        'site_id': creds.get('site_id'),
        'health': health,
        'verified': verify['success'],
        'websites': verify.get('websites', 0) if verify['success'] else 0
    })


@integrations_bp.route('/squarespace/websites', methods=['GET'])
@require_integration_auth
def squarespace_websites():
    """List Squarespace websites."""
    adapter = SquarespaceAdapter(g.user_id)
    
    if not adapter.is_connected():
        return jsonify({'error': 'Squarespace not connected'}), 400
    
    websites = adapter.list_websites()
    return jsonify({'websites': websites})


@integrations_bp.route('/squarespace/products', methods=['GET'])
@require_integration_auth
def squarespace_products():
    """Get products from a Squarespace website.
    
    Query params:
        - website_id: The Squarespace website ID
        - limit: Max products (default 100)
    """
    adapter = SquarespaceAdapter(g.user_id)
    
    if not adapter.is_connected():
        return jsonify({'error': 'Squarespace not connected'}), 400
    
    website_id = request.args.get('website_id')
    limit = int(request.args.get('limit', 100))
    
    if not website_id:
        # Get from stored credentials or first website
        websites = adapter.list_websites()
        if websites:
            website_id = websites[0]['id']
        else:
            return jsonify({'error': 'No website found'}), 400
    
    products = adapter.get_products(website_id, limit)
    return jsonify({
        'website_id': website_id,
        'products': products,
        'count': len(products)
    })


@integrations_bp.route('/squarespace/products/<product_id>/price', methods=['PATCH'])
@require_integration_auth
def squarespace_update_price(product_id):
    """Update product price.
    
    Request body:
        - website_id: Squarespace website ID
        - price_cents: New price in cents (e.g., 2999 for $29.99)
    """
    data = request.get_json() or {}
    website_id = data.get('website_id')
    price_cents = data.get('price_cents')
    
    if not website_id or price_cents is None:
        return jsonify({
            'error': 'website_id and price_cents are required'
        }), 400
    
    adapter = SquarespaceAdapter(g.user_id)
    result = adapter.update_product_price(website_id, product_id, price_cents)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@integrations_bp.route('/squarespace/products/<product_id>/inventory', methods=['PATCH'])
@require_integration_auth
def squarespace_update_inventory(product_id):
    """Update product inventory level.
    
    Request body:
        - website_id: Squarespace website ID
        - quantity: New stock quantity (-1 for unlimited)
    """
    data = request.get_json() or {}
    website_id = data.get('website_id')
    quantity = data.get('quantity')
    
    if not website_id or quantity is None:
        return jsonify({
            'error': 'website_id and quantity are required'
        }), 400
    
    adapter = SquarespaceAdapter(g.user_id)
    result = adapter.update_product_inventory(website_id, product_id, quantity)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@integrations_bp.route('/squarespace/orders', methods=['GET'])
@require_integration_auth
def squarespace_orders():
    """Get orders from a Squarespace website.
    
    Query params:
        - website_id: Squarespace website ID
        - status: Filter by status (FULFILLED, UNFULFILLED, CANCELLED)
    """
    adapter = SquarespaceAdapter(g.user_id)
    
    if not adapter.is_connected():
        return jsonify({'error': 'Squarespace not connected'}), 400
    
    website_id = request.args.get('website_id')
    status = request.args.get('status')
    
    if not website_id:
        websites = adapter.list_websites()
        if websites:
            website_id = websites[0]['id']
        else:
            return jsonify({'error': 'No website found'}), 400
    
    orders = adapter.get_orders(website_id, status)
    return jsonify({
        'website_id': website_id,
        'orders': orders,
        'count': len(orders)
    })


@integrations_bp.route('/squarespace/orders/<order_id>/fulfill', methods=['POST'])
@require_integration_auth
def squarespace_fulfill_order(order_id):
    """Fulfill an order.
    
    Request body:
        - website_id: Squarespace website ID
        - tracking_number: Optional tracking number
        - carrier: Optional carrier (UPS, FEDEX, USPS, etc.)
    """
    data = request.get_json() or {}
    website_id = data.get('website_id')
    tracking_number = data.get('tracking_number')
    carrier = data.get('carrier')
    
    if not website_id:
        return jsonify({'error': 'website_id is required'}), 400
    
    adapter = SquarespaceAdapter(g.user_id)
    result = adapter.fulfill_order(website_id, order_id, tracking_number, carrier)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@integrations_bp.route('/squarespace/sync', methods=['POST'])
@require_integration_auth
def squarespace_sync():
    """Sync products from Squarespace to local database.
    
    Request body:
        - website_id: Squarespace website ID
    """
    data = request.get_json() or {}
    website_id = data.get('website_id')
    
    if not website_id:
        return jsonify({'error': 'website_id is required'}), 400
    
    adapter = SquarespaceAdapter(g.user_id)
    result = adapter.sync_products_to_database(website_id)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@integrations_bp.route('/squarespace/disconnect', methods=['POST'])
@require_integration_auth
def squarespace_disconnect():
    """Disconnect Squarespace account."""
    store = IntegrationCredentialStore(g.user_id)
    store.delete('squarespace')
    
    return jsonify({
        'success': True,
        'message': 'Squarespace disconnected'
    })


# =========================================================================
# SHOPIFY INTEGRATION
# =========================================================================

@integrations_bp.route('/shopify/connect', methods=['POST'])
@require_integration_auth
def connect_shopify():
    """Connect Shopify store with access token.
    
    Request body:
        - shop_domain: Your store domain (e.g., 'mystore.myshopify.com')
        - access_token: Admin API access token (from Shopify admin)
    """
    data = request.get_json() or {}
    
    shop_domain = data.get('shop_domain', '').strip()
    access_token = data.get('access_token', '').strip()
    
    if not shop_domain or not access_token:
        return jsonify({
            'error': 'shop_domain and access_token are required'
        }), 400
    
    # Normalize domain
    shop_domain = shop_domain.replace("https://", "").replace("http://", "").rstrip("/")
    
    # Save credentials
    store = IntegrationCredentialStore(g.user_id)
    store.save('shopify', {
        'shop_domain': shop_domain,
        'access_token': access_token
    })
    
    # Verify connection
    adapter = ShopifyAdapter(g.user_id)
    verify_result = adapter.verify_connection()
    
    if verify_result['success']:
        return jsonify({
            'success': True,
            'message': f"Connected to {verify_result['shop']['name']}!",
            'shop': verify_result['shop'],
            'products_count': verify_result.get('products_count', 0)
        })
    else:
        store.delete('shopify')
        return jsonify({
            'success': False,
            'error': verify_result.get('error', 'Failed to connect')
        }), 400


@integrations_bp.route('/shopify/status', methods=['GET'])
@require_integration_auth
def shopify_status():
    """Get Shopify connection status."""
    store = IntegrationCredentialStore(g.user_id)
    creds = store.get('shopify')
    
    if not creds:
        return jsonify({
            'connected': False,
            'provider': 'shopify'
        })
    
    adapter = ShopifyAdapter(g.user_id)
    verify = adapter.verify_connection()
    health = store.get_health('shopify')
    
    return jsonify({
        'connected': True,
        'provider': 'shopify',
        'shop_domain': creds.get('shop_domain'),
        'health': health,
        'verified': verify['success'],
        'shop': verify.get('shop') if verify['success'] else None,
        'products_count': verify.get('products_count', 0) if verify['success'] else 0
    })


@integrations_bp.route('/shopify/products', methods=['GET'])
@require_integration_auth
def shopify_products():
    """Get products from Shopify store.
    
    Query params:
        - limit: Max products (default 50, max 250)
        - status: Filter by status (active, archived, draft, any)
    """
    adapter = ShopifyAdapter(g.user_id)
    
    if not adapter.is_connected():
        return jsonify({'error': 'Shopify not connected'}), 400
    
    limit = int(request.args.get('limit', 50))
    status = request.args.get('status', 'active')
    
    products = adapter.list_products(limit=min(limit, 250), status=status)
    return jsonify({
        'products': products,
        'count': len(products)
    })


@integrations_bp.route('/shopify/products/<int:product_id>', methods=['GET'])
@require_integration_auth
def shopify_product(product_id):
    """Get single product by ID."""
    adapter = ShopifyAdapter(g.user_id)
    
    if not adapter.is_connected():
        return jsonify({'error': 'Shopify not connected'}), 400
    
    product = adapter.get_product(product_id)
    
    if product:
        return jsonify({'product': product})
    else:
        return jsonify({'error': 'Product not found'}), 404


@integrations_bp.route('/shopify/products/<int:product_id>/price', methods=['PATCH'])
@require_integration_auth
def shopify_update_price(product_id):
    """Update product price.
    
    Request body:
        - price: New price in USD (e.g., 29.99)
    """
    data = request.get_json() or {}
    price = data.get('price')
    
    if price is None:
        return jsonify({'error': 'price is required'}), 400
    
    adapter = ShopifyAdapter(g.user_id)
    result = adapter.update_product_price(product_id, float(price))
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@integrations_bp.route('/shopify/inventory/update', methods=['POST'])
@require_integration_auth
def shopify_update_inventory():
    """Update inventory for one or more variants.
    
    Request body:
        - updates: [{"inventory_item_id": 123, "quantity": 10, "location_id": 456}]
        - location_id: Default location ID (optional if using default)
    """
    data = request.get_json() or {}
    updates = data.get('updates', [])
    default_location = data.get('location_id')
    
    if not updates:
        return jsonify({'error': 'updates array is required'}), 400
    
    adapter = ShopifyAdapter(g.user_id)
    
    # Add default location to updates missing it
    for update in updates:
        if 'location_id' not in update and default_location:
            update['location_id'] = default_location
    
    result = adapter.update_inventory_bulk(updates)
    
    return jsonify(result)


@integrations_bp.route('/shopify/orders', methods=['GET'])
@require_integration_auth
def shopify_orders():
    """Get orders from Shopify store.
    
    Query params:
        - status: Filter (any, open, closed, cancelled)
        - limit: Max orders (default 50, max 250)
    """
    adapter = ShopifyAdapter(g.user_id)
    
    if not adapter.is_connected():
        return jsonify({'error': 'Shopify not connected'}), 400
    
    status = request.args.get('status', 'any')
    limit = int(request.args.get('limit', 50))
    
    orders = adapter.list_orders(status=status, limit=min(limit, 250))
    return jsonify({
        'orders': orders,
        'count': len(orders)
    })


@integrations_bp.route('/shopify/orders/<int:order_id>', methods=['GET'])
@require_integration_auth
def shopify_order(order_id):
    """Get single order by ID."""
    adapter = ShopifyAdapter(g.user_id)
    
    if not adapter.is_connected():
        return jsonify({'error': 'Shopify not connected'}), 400
    
    order = adapter.get_order(order_id)
    
    if order:
        return jsonify({'order': order})
    else:
        return jsonify({'error': 'Order not found'}), 404


@integrations_bp.route('/shopify/orders/<int:order_id>/fulfill', methods=['POST'])
@require_integration_auth
def shopify_fulfill_order(order_id):
    """Fulfill an order.
    
    Request body:
        - tracking_number: Optional tracking number
        - tracking_company: Carrier (ups, fedex, usps, dhl)
        - notify_customer: Send notification (default true)
    """
    data = request.get_json() or {}
    tracking_number = data.get('tracking_number')
    tracking_company = data.get('tracking_company')
    notify_customer = data.get('notify_customer', True)
    
    adapter = ShopifyAdapter(g.user_id)
    result = adapter.fulfill_order(
        order_id, 
        tracking_number, 
        tracking_company,
        notify_customer
    )
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@integrations_bp.route('/shopify/orders/<int:order_id>/partial-fulfill', methods=['POST'])
@require_integration_auth
def shopify_partial_fulfill(order_id):
    """Partially fulfill specific line items.
    
    Request body:
        - line_items: [{"id": line_item_id, "quantity": 2}]
        - tracking_number: Optional tracking
        - tracking_company: Carrier
    """
    data = request.get_json() or {}
    line_items = data.get('line_items', [])
    tracking_number = data.get('tracking_number')
    tracking_company = data.get('tracking_company')
    
    if not line_items:
        return jsonify({'error': 'line_items array is required'}), 400
    
    adapter = ShopifyAdapter(g.user_id)
    result = adapter.create_fulfillment(
        order_id, 
        line_items,
        tracking_number,
        tracking_company
    )
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@integrations_bp.route('/shopify/sync', methods=['POST'])
@require_integration_auth
def shopify_sync():
    """Sync all products and variants to local database."""
    adapter = ShopifyAdapter(g.user_id)
    
    if not adapter.is_connected():
        return jsonify({'error': 'Shopify not connected'}), 400
    
    result = adapter.sync_products_to_database()
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@integrations_bp.route('/shopify/disconnect', methods=['POST'])
@require_integration_auth
def shopify_disconnect():
    """Disconnect Shopify account."""
    store = IntegrationCredentialStore(g.user_id)
    store.delete('shopify')
    
    return jsonify({
        'success': True,
        'message': 'Shopify disconnected'
    })


# =========================================================================
# LIST ALL INTEGRATIONS
# =========================================================================

@integrations_bp.route('', methods=['GET'])
@require_integration_auth
def list_integrations():
    """List all connected integrations for the user."""
    store = IntegrationCredentialStore(g.user_id)
    integrations = store.list()
    
    return jsonify({
        'integrations': integrations
    })


# =========================================================================
# ERROR HANDLERS
# =========================================================================

@integrations_bp.errorhandler(500)
def integration_error(e):
    logger.error(f"Integration error: {e}")
    return jsonify({
        'error': 'An unexpected error occurred. Please try again.'
    }), 500