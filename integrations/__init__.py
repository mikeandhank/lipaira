"""
Lipaira Integrations Package
=============================
Unified interface for external service integrations:
- GoDaddy (DNS, Website Builder)
- Squarespace (Website, Commerce)
- Shopify (E-commerce)
- Cloudflare (DNS)
- And more...
"""

from .credential_store import IntegrationCredentialStore, get_supported_providers
from .network_handler import NetworkHandler, RateLimiter, IdempotencyManager, get_network_handler, get_rate_limiter
from .godaddy import GoDaddyAdapter, get_adapter
from .instacart import InstacartAdapter

__all__ = [
    # Credential management
    'IntegrationCredentialStore',
    'get_supported_providers',
    
    # Network handling
    'NetworkHandler',
    'RateLimiter', 
    'IdempotencyManager',
    'get_network_handler',
    'get_rate_limiter',
    
    # Adapters
    'GoDaddyAdapter',
    'get_adapter',
    'InstacartAdapter',
]

# Provider configuration
PROVIDERS = {
    'godaddy': {
        'name': 'GoDaddy',
        'type': 'registrar',
        'description': 'Domain DNS and Website Builder',
        'auth_method': 'api_key',
    },
    'squarespace': {
        'name': 'Squarespace',
        'type': 'website', 
        'description': 'Website and Commerce',
        'auth_method': 'oauth',
    },
    'shopify': {
        'name': 'Shopify',
        'type': 'ecommerce',
        'description': 'Online Store and Orders',
        'auth_method': 'access_token',
    },
    'cloudflare': {
        'name': 'Cloudflare',
        'type': 'registrar',
        'description': 'DNS and Security',
        'auth_method': 'oauth',
    },
    'namecheap': {
        'name': 'Namecheap',
        'type': 'registrar',
        'description': 'Domain Registration and DNS',
        'auth_method': 'api_key',
    },
    'instacart': {
        'name': 'Instacart',
        'type': 'shopping',
        'description': 'Grocery delivery and pickup',
        'auth_method': 'access_token',
    },
}