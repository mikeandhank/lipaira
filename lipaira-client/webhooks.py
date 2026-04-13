"""
Webhook receiver for Lipaira API server.
Handles incoming webhook events from Shopify, Squarespace, and GoDaddy platforms.
Verifies payload signatures per provider, then dispatches to the appropriate
integration handler (e.g., new order, domain change).
Blueprint: /api/webhooks
"""
import os
import hmac
import hashlib
import base64
import logging
from flask import Blueprint, request, jsonify

log = logging.getLogger(__name__)

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/api/webhooks')


def verify_webhook_signature(provider: str, payload: bytes, signature: str = None) -> bool:
    """
    Verify webhook signature from provider.
    """
    secrets = {
        'shopify': os.environ.get('SHOPIFY_WEBHOOK_SECRET'),
        'squarespace': os.environ.get('SQUARESPACE_WEBHOOK_SECRET'),
        'godaddy': os.environ.get('GODADDY_WEBHOOK_SECRET'),
    }
    
    secret = secrets.get(provider)
    if not secret:
        log.warning(f"No webhook secret configured for {provider}")
        return True  # No verification if not configured
    
    if not signature:
        return False
    
    # Shopify uses HMAC-SHA256 in base64
    if provider == 'shopify':
        computed = base64.b64encode(
            hmac.new(
                secret.encode(),
                payload,
                hashlib.sha256
            ).digest()
        ).decode()
        return hmac.compare_digest(computed, signature or '')
    
    # Others use plain HMAC
    computed = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature or '')


@webhooks_bp.route('/<provider>', methods=['POST'])
def receive_webhook(provider: str):
    """
    Receive and process webhooks from connected platforms.
    """
    # Get signature from headers
    signature = (
        request.headers.get('X-Webhook-Signature') or
        request.headers.get('X-Shopify-Hmac-Sha256') or
        request.headers.get('X-Squarespace-Signature') or
        request.headers.get('Authorization')
    )
    
    payload = request.get_data()
    
    # Verify signature
    if not verify_webhook_signature(provider, payload, signature):
        log.warning(f"Invalid webhook signature from {provider}")
        return jsonify({'error': 'Invalid signature'}), 401
    
    # Parse event data
    try:
        data = request.get_json(force=True) or {}
    except:
        data = {}
    
    # Get event type from headers
    event_type = (
        request.headers.get('X-Shopify-Topic') or
        request.headers.get('X-Squarespace-Topic') or
        data.get('type') or
        'unknown'
    )
    
    log.info(f"Received webhook: {provider}/{event_type}")
    
    # Queue async processing
    import threading
    threading.Thread(
        target=process_webhook_async,
        args=(provider, event_type, data),
        daemon=True
    ).start()
    
    return jsonify({'status': 'received'}), 200


def process_webhook_async(provider: str, event_type: str, data: dict):
    """
    Process webhook in background.
    """
    try:
        handlers = {
            'shopify': {
                'orders/create': handle_shopify_order_created,
                'orders/paid': handle_shopify_order_paid,
                'orders/fulfilled': handle_shopify_order_fulfilled,
                'products/update': handle_shopify_product_update,
                'products/delete': handle_shopify_product_delete,
            },
            'squarespace': {
                'order.create': handle_squarespace_order_created,
                'order.paid': handle_squarespace_order_paid,
                'product.update': handle_squarespace_product_update,
            },
            'godaddy': {
                'domain/transfer_complete': handle_godaddy_transfer,
                'domain/renewal_complete': handle_godaddy_renewal,
            }
        }
        
        provider_handlers = handlers.get(provider, {})
        handler = provider_handlers.get(event_type)
        
        if handler:
            handler(data)
        else:
            log.info(f"Unhandled webhook: {provider}/{event_type}")
            
    except Exception as e:
        log.error(f"Webhook handler failed: {provider}/{event_type}: {e}")
        import traceback
        traceback.print_exc()


# ===== Shopify Handlers =====

def handle_shopify_order_created(data: dict):
    """New Shopify order → notify owner, optionally create QB invoice."""
    order = data.get('order', data)
    order_id = order.get('id')
    order_number = order.get('order_number')
    total = order.get('total_price', '0')
    email = order.get('email', 'unknown')
    customer = order.get('customer', {})
    
    log.info(f"Shopify order created: #{order_number} - ${total}")
    
    # Find user by Shopify domain
    shop_domain = data.get('domain') or data.get('shop_domain')
    if shop_domain:
        user_id = get_user_by_shopify_domain(shop_domain)
    else:
        user_id = None
    
    if user_id:
        # Notify user
        store_notification(
            user_id,
            f"🛒 New Shopify order #{order_number} — ${total} from {customer.get('first_name', email)}"
        )
        
        # Optionally create QB invoice
        # check_user_preference(user_id, 'auto_create_qb_invoice')
    else:
        log.warning(f"No user found for Shopify order {order_number}")


def handle_shopify_order_paid(data: dict):
    """Order paid → update QB invoice status."""
    order = data.get('order', data)
    order_number = order.get('order_number')
    
    log.info(f"Shopify order paid: #{order_number}")
    
    # TODO: Update QB invoice to Paid


def handle_shopify_order_fulfilled(data: dict):
    """Order fulfilled → notify customer, update QB."""
    order = data.get('order', data)
    order_number = order.get('order_number')
    
    log.info(f"Shopify order fulfilled: #{order_number}")
    
    # TODO: Send shipping notification


def handle_shopify_product_update(data: dict):
    """Product updated → sync to QB inventory."""
    product = data.get('product', data)
    product_id = product.get('id')
    title = product.get('title')
    
    log.info(f"Shopify product updated: {title} ({product_id})")


def handle_shopify_product_delete(data: dict):
    """Product deleted → mark inactive in QB."""
    product = data.get('product', data)
    product_id = product.get('id')
    
    log.info(f"Shopify product deleted: {product_id}")


# ===== Squarespace Handlers =====

def handle_squarespace_order_created(data: dict):
    """New Squarespace order."""
    order = data.get('order', data)
    order_id = order.get('id')
    total = order.get('grandTotal', '0')
    
    log.info(f"Squarespace order created: {order_id} - ${total}")
    
    store_notification(
        user_id,
        f"🛒 New Squarespace order — ${total}"
    )


def handle_squarespace_order_paid(data: dict):
    """Squarespace order paid."""
    order = data.get('order', data)
    order_id = order.get('id')
    
    log.info(f"Squarespace order paid: {order_id}")


def handle_squarespace_product_update(data: dict):
    """Product updated on Squarespace."""
    product = data.get('product', data)
    
    log.info(f"Squarespace product updated")


# ===== GoDaddy Handlers =====

def handle_godaddy_transfer(data: dict):
    """Domain transfer complete."""
    domain = data.get('domain', 'unknown')
    log.info(f"GoDaddy domain transferred: {domain}")


def handle_godaddy_renewal(data: dict):
    """Domain renewal complete."""
    domain = data.get('domain', 'unknown')
    log.info(f"GoDaddy domain renewed: {domain}")


# ===== Helper Functions =====

def get_user_by_shopify_domain(shop_domain: str) -> str:
    """
    Find user by connected Shopify domain.
    """
    from db import get_user_conn
    
    try:
        with get_user_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT user_id FROM user_integrations
                    WHERE provider = 'shopify'
                    AND context->>'domain' = %s
                """, (shop_domain,))
                row = cur.fetchone()
                return row[0] if row else None
    except Exception as e:
        log.error(f"Failed to get user by shopify domain: {e}")
        return None


def store_notification(user_id: str, message: str):
    """
    Store notification for user (push to dashboard).
    """
    # TODO: Implement notification storage
    log.info(f"Notification for {user_id}: {message}")


def check_user_preference(user_id: str, preference: str) -> bool:
    """
    Check if user has a preference enabled.
    """
    # TODO: Implement preference check
    return False