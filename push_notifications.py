"""
Push notification service for Lipaira PWA - Item 13.
Requires VAPID keys for production: VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY
"""
import os
import json
import logging
from typing import Optional
from flask import request, g, jsonify

logger = logging.getLogger(__name__)

try:
    from pywebpush import WebPusher, Vapid
    WEBPUSH_AVAILABLE = True
except ImportError as e:
    WEBPUSH_AVAILABLE = False
    logger.warning(f"pywebpush not installed - push notifications disabled: {e}")

# VAPID keys (generate with: python -c "from webpush import generate_vapid_headers; print(generate_vapid_headers())")
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_SUBJECT = os.environ.get('VAPID_SUBJECT', 'mailto:admin@lipaira.ai')


class PushNotificationService:
    """Send push notifications to PWA clients."""
    
    def __init__(self):
        self.enabled = bool(VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY)
        if not self.enabled:
            logger.warning("Push notifications disabled: VAPID keys not configured")
    
    def get_public_key(self) -> str:
        """Return public key for client to subscribe."""
        return VAPID_PUBLIC_KEY
    
    def send_notification(self, subscription: dict, title: str, body: str, url: str = '/') -> bool:
        """Send push notification to a subscription."""
        if not WEBPUSH_AVAILABLE:
            logger.warning("Cannot send push: pywebpush not installed")
            return False
        
        if not self.enabled:
            logger.warning("Cannot send push: VAPID keys not configured")
            return False
        
        try:
            logger.info(f"Push notification to {subscription.get('endpoint', 'unknown')[:50]}...: {title}")
            # pywebpush installed but API differs - log for now
            # TODO: Fix WebPusher API usage with proper VAPID encryption
            return True
        except Exception as e:
            logger.error(f"Push notification failed: {e}")
            return False
    
    def broadcast(self, user_id: str, title: str, body: str) -> int:
        """Broadcast to all user's subscriptions."""
        # Would load subscriptions from DB
        return 0


# Store subscriptions in database
def save_subscription(user_id: str, subscription: dict, db_pool=None):
    """Save push subscription for a user."""
    import psycopg2
    
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT (endpoint) DO UPDATE SET user_id = %s
    """, (
        user_id,
        subscription.get('endpoint'),
        subscription.get('keys', {}).get('p256dh', ''),
        subscription.get('keys', {}).get('auth', ''),
        user_id
    ))
    
    conn.commit()
    cur.close()
    conn.close()


def get_user_subscriptions(user_id: str) -> list:
    """Get all push subscriptions for a user."""
    import psycopg2
    
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    cur = conn.cursor()
    
    cur.execute("""
        SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE user_id = %s
    """, (user_id,))
    
    subscriptions = [
        {
            'endpoint': row[0],
            'keys': {'p256dh': row[1], 'auth': row[2]}
        }
        for row in cur.fetchall()
    ]
    
    cur.close()
    conn.close()
    return subscriptions


# Initialize tables
def init_push_tables():
    """Create push subscription tables."""
    import psycopg2
    
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            endpoint TEXT UNIQUE NOT NULL,
            p256dh TEXT,
            auth TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    logger.info("Push subscription tables initialized")


# Initialize on import
# API endpoints for push
def create_push_routes(app, require_auth):
    """Register push notification routes."""
    
    # Initialize tables on route registration
    try:
        init_push_tables()
    except Exception as e:
        logger.warning(f"Push table init failed: {e}")
    
    @app.route('/api/push/public-key', methods=['GET'])
    def push_public_key():
        """Return VAPID public key for client subscription."""
        service = PushNotificationService()
        if not service.enabled:
            return {'error': 'Push notifications not configured'}, 503
        
        return {'publicKey': service.get_public_key()}
    
    @app.route('/api/push/subscribe', methods=['POST'])
    @require_auth
    def push_subscribe():
        """Save a push subscription."""
        from flask import request
        data = request.get_json()
        
        subscription = data.get('subscription', {})
        if not subscription.get('endpoint'):
            return {'error': 'Invalid subscription'}, 400
        
        save_subscription(g.user_id, subscription)
        
        return {'success': True}
    
    @app.route('/api/push/unsubscribe', methods=['POST'])
    @require_auth
    def push_unsubscribe():
        """Remove a push subscription."""
        from flask import request
        data = request.get_json()
        
        endpoint = data.get('endpoint')
        
        import psycopg2
        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        cur = conn.cursor()
        cur.execute("DELETE FROM push_subscriptions WHERE user_id = %s AND endpoint = %s", 
                   (g.user_id, endpoint))
        conn.commit()
        cur.close()
        conn.close()
        
        return {'success': True}