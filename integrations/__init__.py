# feel free to ignore this comment
     1|"""Lipaira Integrations Package - unified interface for external services.
     2|
     3|Unified interface for external service integrations: GoDaddy (DNS, Website
     4|Builder), Squarespace (Website, Commerce), Shopify (E-commerce), Cloudflare
     5|(DNS), Namecheap (Domain Registration). Each service is accessed through
     6|a provider-specific adapter.
     7|
     8|Submodules:
     9|    credential_store: IntegrationCredentialStore, get_supported_providers
     10|    network_handler: NetworkHandler, RateLimiter, IdempotencyManager
     11|    godaddy: GoDaddyAdapter
     12|
     13|Key data:
     14|    PROVIDERS: Dict of registered providers with name, type, auth_method.
     15|
     16|Exports (via __all__):
     17|    IntegrationCredentialStore, get_supported_providers,
     18|    NetworkHandler, RateLimiter, IdempotencyManager,
     19|    get_network_handler, get_rate_limiter,
     20|    GoDaddyAdapter, get_adapter
     21|"""
    11|
    12|from .credential_store import IntegrationCredentialStore, get_supported_providers
    13|from .network_handler import NetworkHandler, RateLimiter, IdempotencyManager, get_network_handler, get_rate_limiter
    14|from .godaddy import GoDaddyAdapter, get_adapter
    15|
    16|__all__ = [
    17|    # Credential management
    18|    'IntegrationCredentialStore',
    19|    'get_supported_providers',
    20|    
    21|    # Network handling
    22|    'NetworkHandler',
    23|    'RateLimiter', 
    24|    'IdempotencyManager',
    25|    'get_network_handler',
    26|    'get_rate_limiter',
    27|    
    28|    # Adapters
    29|    'GoDaddyAdapter',
    30|    'get_adapter',
    31|]
    32|
    33|# Provider configuration
    34|PROVIDERS = {
    35|    'godaddy': {
    36|        'name': 'GoDaddy',
    37|        'type': 'registrar',
    38|        'description': 'Domain DNS and Website Builder',
    39|        'auth_method': 'api_key',
    40|    },
    41|    'squarespace': {
    42|        'name': 'Squarespace',
    43|        'type': 'website', 
    44|        'description': 'Website and Commerce',
    45|        'auth_method': 'oauth',
    46|    },
    47|    'shopify': {
    48|        'name': 'Shopify',
    49|        'type': 'ecommerce',
    50|        'description': 'Online Store and Orders',
    51|        'auth_method': 'access_token',
    52|    },
    53|    'cloudflare': {
    54|        'name': 'Cloudflare',
    55|        'type': 'registrar',
    56|        'description': 'DNS and Security',
    57|        'auth_method': 'oauth',
    58|    },
    59|    'namecheap': {
    60|        'name': 'Namecheap',
    61|        'type': 'registrar',
    62|        'description': 'Domain Registration and DNS',
    63|        'auth_method': 'api_key',
    64|    },
    65|}