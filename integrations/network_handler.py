"""
Network Handler
===============
Handles external API calls with rate limiting, retry logic,
and user-friendly error translation.
"""

import os
import time
import json
import logging
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Callable, Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter per provider.
    Prevents hitting provider rate limits.
    
    Usage:
        limiter = RateLimiter()
        
        # Try to acquire token
        if limiter.acquire("godaddy", 60):
            # Make API call
            pass
        else:
            # Wait
            time.sleep(limiter.wait_time("godaddy"))
    """

    def __init__(self):
        # {provider: (last_request_time, tokens_remaining)}
        self._buckets: Dict[str, tuple] = {}
        self._lock = threading.Lock()

    def acquire(self, provider: str, rate_limit: int, tokens: int = 1) -> bool:
        """
        Try to acquire tokens for a provider.
        
        Args:
            provider: Provider name
            rate_limit: Tokens per minute (from PROVIDER_CONFIG)
            tokens: Number of tokens to acquire (default 1)
            
        Returns:
            True if call can proceed, False if need to wait
        """
        with self._lock:
            now = datetime.now()
            key = provider

            if key not in self._buckets:
                # First call - initialize bucket
                self._buckets[key] = (now, rate_limit - tokens)
                return True

            last_time, tokens_remaining = self._buckets[key]

            # Reset bucket if 1 minute has passed
            if (now - last_time) > timedelta(minutes=1):
                self._buckets[key] = (now, rate_limit - tokens)
                return True

            # Check if we have enough tokens
            if tokens_remaining >= tokens:
                self._buckets[key] = (last_time, tokens_remaining - tokens)
                return True

            # Need to wait for bucket to refill
            return False

    def wait_time(self, provider: str) -> float:
        """Calculate seconds to wait before next token."""
        with self._lock:
            if provider not in self._buckets:
                return 0

            last_time, tokens_remaining = self._buckets[provider]
            elapsed = (datetime.now() - last_time).total_seconds()

            if elapsed >= 60:  # Bucket reset
                return 0

            # Calculate time until bucket fills enough for 1 token
            # tokens_per_second = rate_limit / 60
            return max(0, 60 - elapsed)

    def reset(self, provider: str = None):
        """Reset rate limit for provider (or all)."""
        with self._lock:
            if provider:
                self._buckets.pop(provider, None)
            else:
                self._buckets.clear()


# Error message translations
ERROR_TRANSLATIONS = {
    "godaddy": {
        "400": "The request wasn't valid. Check the domain name and try again.",
        "401": "Your GoDaddy API key may have expired. Try reconnecting in Settings.",
        "403": "Don't have permission to manage this domain in GoDaddy.",
        "404": "Couldn't find that domain in your GoDaddy account.",
        "422": "The DNS record value isn't valid. Check the format and try again.",
        "429": "GoDaddy is busy. Waiting and trying again...",
        "503": "GoDaddy is temporarily unavailable. Trying again in a moment...",
    },
    "squarespace": {
        "400": "The website data wasn't valid. Try a simpler change.",
        "401": "Your Squarespace connection expired. Try reconnecting in Settings.",
        "403": "Don't have permission to edit this site.",
        "404": "Couldn't find that page on your Squarespace site.",
        "429": "Squarespace is busy. Waiting and trying again...",
    },
    "shopify": {
        "400": "The product data wasn't valid. Check the price and try again.",
        "401": "Your Shopify access may have expired. Try reconnecting in Settings.",
        "403": "Don't have permission to manage this store.",
        "404": "Couldn't find that product in your store.",
        "429": "Shopify is busy. Waiting and trying again...",
    },
    "cloudflare": {
        "400": "The DNS record wasn't valid.",
        "401": "Your Cloudflare token may have expired.",
        "403": "Don't have permission to manage this domain.",
        "404": "Couldn't find that domain in Cloudflare.",
    },
    "namecheap": {
        "400": "The request wasn't valid.",
        "401": "Your Namecheap API key may have expired.",
        "403": "Don't have permission to manage this domain.",
        "404": "Couldn't find that domain in your Namecheap account.",
    }
}


class NetworkHandler:
    """
    Handles external API calls with rate limiting and retry logic.
    
    Usage:
        handler = NetworkHandler()
        
        def make_request():
            return requests.get("https://api.godaddy.com/...")
        
        result = handler.call("godaddy", 60, make_request)
        
        if result["success"]:
            data = result["data"]
        else:
            print(result["error"])  # User-friendly message
    """

    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Lipaira/1.0",
            "Accept": "application/json",
        })

    def call(self, provider: str, rate_limit: int,
             request_fn: Callable[[], requests.Response],
             retry_count: int = 3) -> Dict:
        """
        Make an API call with rate limiting and retry logic.

        Args:
            provider: Provider name for rate limiting and error translation
            rate_limit: Calls per minute allowed
            request_fn: Function that returns requests.Response
            retry_count: Number of retries on failure

        Returns:
            {"success": bool, "data": Any, "error": str}
        """

        # Acquire rate limit token, waiting if necessary
        while not self.rate_limiter.acquire(provider, rate_limit):
            wait = self.rate_limiter.wait_time(provider)
            logger.info(f"Rate limited {provider}, waiting {wait:.1f}s")
            time.sleep(min(wait, 5))  # Cap wait at 5 seconds

        # Attempt request with retries
        last_error = None
        for attempt in range(retry_count):
            try:
                response = request_fn()

                if response.ok:
                    try:
                        return {"success": True, "data": response.json()}
                    except json.JSONDecodeError:
                        return {"success": True, "data": response.text}

                # Handle rate limit response from provider
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Provider {provider} returned 429, waiting {retry_after}s")
                    time.sleep(min(retry_after, 30))
                    continue

                # Handle specific errors
                if response.status_code >= 500:
                    last_error = f"{provider.title()} is having server issues. Trying again..."
                    logger.warning(f"Server error {response.status_code} from {provider}")
                else:
                    # Client error - translate to user-friendly message
                    return {
                        "success": False,
                        "error": self._translate_error(provider, response)
                    }

            except requests.exceptions.Timeout:
                last_error = "The service took too long to respond. Trying again..."
                logger.warning(f"Timeout on {provider} attempt {attempt + 1}")

            except requests.exceptions.ConnectionError as e:
                last_error = f"Couldn't connect to {provider.title()}. Checking network..."
                logger.warning(f"Connection error on {provider}: {e}")

            except Exception as e:
                last_error = f"An unexpected error occurred: {str(e)}"
                logger.error(f"Unexpected error on {provider}: {e}")

            # Exponential backoff
            if attempt < retry_count - 1:
                wait_time = 2 ** attempt
                logger.info(f"Retrying {provider} in {wait_time}s...")
                time.sleep(wait_time)

        return {"success": False, "error": last_error or "Failed after multiple attempts"}

    def _translate_error(self, provider: str, 
                         response: requests.Response) -> str:
        """Translate provider errors to user-friendly messages."""
        
        status = str(response.status_code)
        provider_errors = ERROR_TRANSLATIONS.get(provider, {})

        if status in provider_errors:
            return provider_errors[status]

        # Try to get error message from response body
        try:
            error_data = response.json()
            if "message" in error_data:
                return f"{provider.title()}: {error_data['message']}"
            if "error" in error_data:
                return f"{provider.title()}: {error_data['error']}"
        except (json.JSONDecodeError, AttributeError):
            pass

        # Generic fallback
        return f"Got an error from {provider.title()} (code: {status}). Try again in a moment."


class IdempotencyManager:
    """
    Prevents duplicate operations for DNS records and products.
    
    Usage:
        idempotency = IdempotencyManager(user_id)
        
        # Check before creating
        if not idempotency.check("godaddy", "add_dns_record", "davesplumbing.com", "TXT:@"):
            return {"error": "Already done recently"}
        
        # Proceed with operation
        ...
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._cache = {}
        self._lock = threading.Lock()

    def _make_key(self, provider: str, operation: str, 
                  identifier: str) -> str:
        """Create deterministic key for operation."""
        data = f"{self.user_id}:{provider}:{operation}:{identifier}"
        # Simple hash for cache key
        return str(hash(data))

    def check(self, provider: str, operation: str, 
              identifier: str, ttl_seconds: int = 300) -> bool:
        """
        Check if operation was recently performed.
        
        Args:
            provider: Provider name
            operation: Operation type (add_dns_record, update_product, etc.)
            identifier: Unique identifier for the entity
            ttl_seconds: How long to consider this a duplicate
            
        Returns:
            True if this is a new operation (proceed)
            False if duplicate (skip)
        """
        key = self._make_key(provider, operation, identifier)

        with self._lock:
            if key in self._cache:
                cached_time = self._cache[key]
                if (datetime.now() - cached_time).total_seconds() < ttl_seconds:
                    logger.info(f"Idempotency check: duplicate {provider}:{operation}:{identifier}")
                    return False  # Duplicate

            self._cache[key] = datetime.now()
            return True  # New operation

    def dns_record_exists(self, domain: str, record_type: str, 
                          name: str, value: str) -> bool:
        """Check if identical DNS record already exists in database."""
        from .credential_store import get_db_connection
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id FROM dns_records 
                    WHERE user_id = %s 
                    AND domain = %s 
                    AND record_type = %s 
                    AND name = %s 
                    AND value = %s
                """, (self.user_id, domain, record_type, name, value))
                return cur.fetchone() is not None

    def log_action(self, provider: str, action: str, 
                   status: str, details: dict = None):
        """Log action to database for audit trail."""
        from .credential_store import get_db_connection
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO integration_sync_log
                    (user_id, provider, action, status, details)
                    VALUES (%s, %s, %s, %s, %s)
                """, (self.user_id, provider, action, status, 
                      json.dumps(details) if details else None))
                conn.commit()


# Global instances (singleton per process)
_rate_limiter = None
_network_handler = None


def get_rate_limiter() -> RateLimiter:
    """Get global RateLimiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def get_network_handler() -> NetworkHandler:
    """Get global NetworkHandler instance."""
    global _network_handler
    if _network_handler is None:
        _network_handler = NetworkHandler()
    return _network_handler