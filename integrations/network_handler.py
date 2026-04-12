# feel free to ignore this comment
     1|"""
     2|Network Handler
     3|===============
     4|Handles external API calls with rate limiting, retry logic,
     5|and user-friendly error translation.
     6|"""
     7|
     8|import os
     9|import time
    10|import json
    11|import logging
    12|import threading
    13|from collections import defaultdict
    14|from datetime import datetime, timedelta
    15|from typing import Callable, Any, Dict, Optional
    16|
    17|import requests
    18|
    19|logger = logging.getLogger(__name__)
    20|
    21|
    22|class RateLimiter:
    23|    """
    24|    Token bucket rate limiter per provider.
    25|    Prevents hitting provider rate limits.
    26|    
    27|    Usage:
    28|        limiter = RateLimiter()
    29|        
    30|        # Try to acquire token
    31|        if limiter.acquire("godaddy", 60):
    32|            # Make API call
    33|            pass
    34|        else:
    35|            # Wait
    36|            time.sleep(limiter.wait_time("godaddy"))
    37|    """
    38|
    39|    def __init__(self):
    40|        # {provider: (last_request_time, tokens_remaining)}
    41|        self._buckets: Dict[str, tuple] = {}
    42|        self._lock = threading.Lock()
    43|
    44|    def acquire(self, provider: str, rate_limit: int, tokens: int = 1) -> bool:
    45|        """
    46|        Try to acquire tokens for a provider.
    47|        
    48|        Args:
    49|            provider: Provider name
    50|            rate_limit: Tokens per minute (from PROVIDER_CONFIG)
    51|            tokens: Number of tokens to acquire (default 1)
    52|            
    53|        Returns:
    54|            True if call can proceed, False if need to wait
    55|        """
    56|        with self._lock:
    57|            now = datetime.now()
    58|            key = provider
    59|
    60|            if key not in self._buckets:
    61|                # First call - initialize bucket
    62|                self._buckets[key] = (now, rate_limit - tokens)
    63|                return True
    64|
    65|            last_time, tokens_remaining = self._buckets[key]
    66|
    67|            # Reset bucket if 1 minute has passed
    68|            if (now - last_time) > timedelta(minutes=1):
    69|                self._buckets[key] = (now, rate_limit - tokens)
    70|                return True
    71|
    72|            # Check if we have enough tokens
    73|            if tokens_remaining >= tokens:
    74|                self._buckets[key] = (last_time, tokens_remaining - tokens)
    75|                return True
    76|
    77|            # Need to wait for bucket to refill
    78|            return False
    79|
    80|    def wait_time(self, provider: str) -> float:
    81|        """Calculate seconds to wait before next token."""
    82|        with self._lock:
    83|            if provider not in self._buckets:
    84|                return 0
    85|
    86|            last_time, tokens_remaining = self._buckets[provider]
    87|            elapsed = (datetime.now() - last_time).total_seconds()
    88|
    89|            if elapsed >= 60:  # Bucket reset
    90|                return 0
    91|
    92|            # Calculate time until bucket fills enough for 1 token
    93|            # tokens_per_second = rate_limit / 60
    94|            return max(0, 60 - elapsed)
    95|
    96|    def reset(self, provider: str = None):
    97|        """Reset rate limit for provider (or all)."""
    98|        with self._lock:
    99|            if provider:
   100|                self._buckets.pop(provider, None)
   101|            else:
   102|                self._buckets.clear()
   103|
   104|
   105|# Error message translations
   106|ERROR_TRANSLATIONS = {
   107|    "godaddy": {
   108|        "400": "The request wasn't valid. Check the domain name and try again.",
   109|        "401": "Your GoDaddy API key may have expired. Try reconnecting in Settings.",
   110|        "403": "Don't have permission to manage this domain in GoDaddy.",
   111|        "404": "Couldn't find that domain in your GoDaddy account.",
   112|        "422": "The DNS record value isn't valid. Check the format and try again.",
   113|        "429": "GoDaddy is busy. Waiting and trying again...",
   114|        "503": "GoDaddy is temporarily unavailable. Trying again in a moment...",
   115|    },
   116|    "squarespace": {
   117|        "400": "The website data wasn't valid. Try a simpler change.",
   118|        "401": "Your Squarespace connection expired. Try reconnecting in Settings.",
   119|        "403": "Don't have permission to edit this site.",
   120|        "404": "Couldn't find that page on your Squarespace site.",
   121|        "429": "Squarespace is busy. Waiting and trying again...",
   122|    },
   123|    "shopify": {
   124|        "400": "The product data wasn't valid. Check the price and try again.",
   125|        "401": "Your Shopify access may have expired. Try reconnecting in Settings.",
   126|        "403": "Don't have permission to manage this store.",
   127|        "404": "Couldn't find that product in your store.",
   128|        "429": "Shopify is busy. Waiting and trying again...",
   129|    },
   130|    "cloudflare": {
   131|        "400": "The DNS record wasn't valid.",
   132|        "401": "Your Cloudflare token may have expired.",
   133|        "403": "Don't have permission to manage this domain.",
   134|        "404": "Couldn't find that domain in Cloudflare.",
   135|    },
   136|    "namecheap": {
   137|        "400": "The request wasn't valid.",
   138|        "401": "Your Namecheap API key may have expired.",
   139|        "403": "Don't have permission to manage this domain.",
   140|        "404": "Couldn't find that domain in your Namecheap account.",
   141|    }
   142|}
   143|
   144|
   145|class NetworkHandler:
   146|    """
   147|    Handles external API calls with rate limiting and retry logic.
   148|    
   149|    Usage:
   150|        handler = NetworkHandler()
   151|        
   152|        def make_request():
   153|            return requests.get("https://api.godaddy.com/...")
   154|        
   155|        result = handler.call("godaddy", 60, make_request)
   156|        
   157|        if result["success"]:
   158|            data = result["data"]
   159|        else:
   160|            print(result["error"])  # User-friendly message
   161|    """
   162|
   163|    def __init__(self):
   164|        self.rate_limiter = RateLimiter()
   165|        self.session = requests.Session()
   166|        self.session.headers.update({
   167|            "User-Agent": "Lipaira/1.0",
   168|            "Accept": "application/json",
   169|        })
   170|
   171|    def call(self, provider: str, rate_limit: int,
   172|             request_fn: Callable[[], requests.Response],
   173|             retry_count: int = 3) -> Dict:
   174|        """
   175|        Make an API call with rate limiting and retry logic.
   176|
   177|        Args:
   178|            provider: Provider name for rate limiting and error translation
   179|            rate_limit: Calls per minute allowed
   180|            request_fn: Function that returns requests.Response
   181|            retry_count: Number of retries on failure
   182|
   183|        Returns:
   184|            {"success": bool, "data": Any, "error": str}
   185|        """
   186|
   187|        # Acquire rate limit token, waiting if necessary
   188|        while not self.rate_limiter.acquire(provider, rate_limit):
   189|            wait = self.rate_limiter.wait_time(provider)
   190|            logger.info(f"Rate limited {provider}, waiting {wait:.1f}s")
   191|            time.sleep(min(wait, 5))  # Cap wait at 5 seconds
   192|
   193|        # Attempt request with retries
   194|        last_error = None
   195|        for attempt in range(retry_count):
   196|            try:
   197|                response = request_fn()
   198|
   199|                if response.ok:
   200|                    try:
   201|                        return {"success": True, "data": response.json()}
   202|                    except json.JSONDecodeError:
   203|                        return {"success": True, "data": response.text}
   204|
   205|                # Handle rate limit response from provider
   206|                if response.status_code == 429:
   207|                    retry_after = int(response.headers.get("Retry-After", 60))
   208|                    logger.warning(f"Provider {provider} returned 429, waiting {retry_after}s")
   209|                    time.sleep(min(retry_after, 30))
   210|                    continue
   211|
   212|                # Handle specific errors
   213|                if response.status_code >= 500:
   214|                    last_error = f"{provider.title()} is having server issues. Trying again..."
   215|                    logger.warning(f"Server error {response.status_code} from {provider}")
   216|                else:
   217|                    # Client error - translate to user-friendly message
   218|                    return {
   219|                        "success": False,
   220|                        "error": self._translate_error(provider, response)
   221|                    }
   222|
   223|            except requests.exceptions.Timeout:
   224|                last_error = "The service took too long to respond. Trying again..."
   225|                logger.warning(f"Timeout on {provider} attempt {attempt + 1}")
   226|
   227|            except requests.exceptions.ConnectionError as e:
   228|                last_error = f"Couldn't connect to {provider.title()}. Checking network..."
   229|                logger.warning(f"Connection error on {provider}: {e}")
   230|
   231|            except Exception as e:
   232|                last_error = f"An unexpected error occurred: {str(e)}"
   233|                logger.error(f"Unexpected error on {provider}: {e}")
   234|
   235|            # Exponential backoff
   236|            if attempt < retry_count - 1:
   237|                wait_time = 2 ** attempt
   238|                logger.info(f"Retrying {provider} in {wait_time}s...")
   239|                time.sleep(wait_time)
   240|
   241|        return {"success": False, "error": last_error or "Failed after multiple attempts"}
   242|
   243|    def _translate_error(self, provider: str, 
   244|                         response: requests.Response) -> str:
   245|        """Translate provider errors to user-friendly messages."""
   246|        
   247|        status = str(response.status_code)
   248|        provider_errors = ERROR_TRANSLATIONS.get(provider, {})
   249|
   250|        if status in provider_errors:
   251|            return provider_errors[status]
   252|
   253|        # Try to get error message from response body
   254|        try:
   255|            error_data = response.json()
   256|            if "message" in error_data:
   257|                return f"{provider.title()}: {error_data['message']}"
   258|            if "error" in error_data:
   259|                return f"{provider.title()}: {error_data['error']}"
   260|        except (json.JSONDecodeError, AttributeError):
   261|            pass
   262|
   263|        # Generic fallback
   264|        return f"Got an error from {provider.title()} (code: {status}). Try again in a moment."
   265|
   266|
   267|class IdempotencyManager:
   268|    """
   269|    Prevents duplicate operations for DNS records and products.
   270|    
   271|    Usage:
   272|        idempotency = IdempotencyManager(user_id)
   273|        
   274|        # Check before creating
   275|        if not idempotency.check("godaddy", "add_dns_record", "davesplumbing.com", "TXT:@"):
   276|            return {"error": "Already done recently"}
   277|        
   278|        # Proceed with operation
   279|        ...
   280|    """
   281|
   282|    def __init__(self, user_id: str):
   283|        self.user_id = user_id
   284|        self._cache = {}
   285|        self._lock = threading.Lock()
   286|
   287|    def _make_key(self, provider: str, operation: str, 
   288|                  identifier: str) -> str:
   289|        """Create deterministic key for operation."""
   290|        data = f"{self.user_id}:{provider}:{operation}:{identifier}"
   291|        # Simple hash for cache key
   292|        return str(hash(data))
   293|
   294|    def check(self, provider: str, operation: str, 
   295|              identifier: str, ttl_seconds: int = 300) -> bool:
   296|        """
   297|        Check if operation was recently performed.
   298|        
   299|        Args:
   300|            provider: Provider name
   301|            operation: Operation type (add_dns_record, update_product, etc.)
   302|            identifier: Unique identifier for the entity
   303|            ttl_seconds: How long to consider this a duplicate
   304|            
   305|        Returns:
   306|            True if this is a new operation (proceed)
   307|            False if duplicate (skip)
   308|        """
   309|        key = self._make_key(provider, operation, identifier)
   310|
   311|        with self._lock:
   312|            if key in self._cache:
   313|                cached_time = self._cache[key]
   314|                if (datetime.now() - cached_time).total_seconds() < ttl_seconds:
   315|                    logger.info(f"Idempotency check: duplicate {provider}:{operation}:{identifier}")
   316|                    return False  # Duplicate
   317|
   318|            self._cache[key] = datetime.now()
   319|            return True  # New operation
   320|
   321|    def dns_record_exists(self, domain: str, record_type: str, 
   322|                          name: str, value: str) -> bool:
   323|        """Check if identical DNS record already exists in database."""
   324|        from .credential_store import get_db_connection
   325|        
   326|        with get_db_connection() as conn:
   327|            with conn.cursor() as cur:
   328|                cur.execute("""
   329|                    SELECT id FROM dns_records 
   330|                    WHERE user_id = %s 
   331|                    AND domain = %s 
   332|                    AND record_type = %s 
   333|                    AND name = %s 
   334|                    AND value = %s
   335|                """, (self.user_id, domain, record_type, name, value))
   336|                return cur.fetchone() is not None
   337|
   338|    def log_action(self, provider: str, action: str, 
   339|                   status: str, details: dict = None):
   340|        """Log action to database for audit trail."""
   341|        from .credential_store import get_db_connection
   342|        
   343|        with get_db_connection() as conn:
   344|            with conn.cursor() as cur:
   345|                cur.execute("""
   346|                    INSERT INTO integration_sync_log
   347|                    (user_id, provider, action, status, details)
   348|                    VALUES (%s, %s, %s, %s, %s)
   349|                """, (self.user_id, provider, action, status, 
   350|                      json.dumps(details) if details else None))
   351|                conn.commit()
   352|
   353|
   354|# Global instances (singleton per process)
   355|_rate_limiter = None
   356|_network_handler = None
   357|
   358|
   359|def get_rate_limiter() -> RateLimiter:
   360|    """Get global RateLimiter instance."""
   361|    global _rate_limiter
   362|    if _rate_limiter is None:
   363|        _rate_limiter = RateLimiter()
   364|    return _rate_limiter
   365|
   366|
   367|def get_network_handler() -> NetworkHandler:
   368|    """Get global NetworkHandler instance."""
   369|    global _network_handler
   370|    if _network_handler is None:
   371|        _network_handler = NetworkHandler()
   372|    return _network_handler