"""
Rate-Limited Executor
======================
Executes platform operations with rate limiting and parallel execution.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


# Rate limits per platform (requests per minute)
RATE_LIMITS = {
    "godaddy": 60,
    "squarespace": 600,
    "shopify": 2400,
    "google": 60,
    "quickbooks": 100,
}

# Delays between requests (in seconds)
REQUEST_DELAYS = {platform: 60.0 / rate for platform, rate in RATE_LIMITS.items()}


@dataclass
class PlatformAction:
    """An action to be performed on a platform."""
    platform: str
    adapter: Any  # The adapter instance
    method_name: str  # Method to call
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    result: Any = None
    error: Optional[str] = None
    success: bool = False


@dataclass
class ExecutionResult:
    """Result of executing an intent across platforms."""
    success: bool
    intent_hash: str  # For verification
    actions: List[PlatformAction]
    total_actions: int
    failed_actions: int
    summary: str
    duration_ms: int


class RateLimitedExecutor:
    """
    Executes platform actions with rate limiting and parallel execution.
    """
    
    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self.last_request_time: Dict[str, float] = {}
        self._lock = asyncio.Lock()
    
    def _get_delay(self, platform: str) -> float:
        """Get delay for a platform."""
        return REQUEST_DELAYS.get(platform, 1.0)
    
    async def _wait_for_rate_limit(self, platform: str):
        """Wait if necessary to respect rate limits."""
        async with self._lock:
            now = time.time()
            last = self.last_request_time.get(platform, 0)
            delay = self._get_delay(platform)
            
            wait_time = delay - (now - last)
            if wait_time > 0:
                logger.info(f"Rate limiting {platform}: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
            
            self.last_request_time[platform] = time.time()
    
    async def execute_single(self, action: PlatformAction) -> PlatformAction:
        """Execute a single platform action with rate limiting."""
        await self._wait_for_rate_limit(action.platform)
        
        try:
            method = getattr(action.adapter, action.method_name)
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(
                    executor,
                    lambda: method(*action.args, **action.kwargs)
                )
            
            action.result = result
            action.success = True
            
        except Exception as e:
            logger.error(f"Action failed on {action.platform}: {e}")
            action.error = str(e)
            action.success = False
        
        return action
    
    async def execute_parallel(self, actions: List[PlatformAction]) -> List[PlatformAction]:
        """Execute multiple actions in parallel (respecting rate limits per platform)."""
        # Group by platform to avoid rate limit collisions
        platform_groups: Dict[str, List[PlatformAction]] = {}
        for action in actions:
            if action.platform not in platform_groups:
                platform_groups[action.platform] = []
            platform_groups[action.platform].append(action)
        
        # Execute each platform's actions
        tasks = []
        for platform, group in platform_groups.items():
            # For each platform, execute sequentially (to respect rate limits)
            for action in group:
                tasks.append(self.execute_single(action))
        
        # Wait for all
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                actions[i].error = str(result)
                actions[i].success = False
        
        return actions


class CapabilityResolver:
    """
    Resolves which platforms can handle a given intent based on capabilities.
    """
    
    # Capability to action mapping
    CAPABILITIES = {
        "update_prices": ["squarespace", "shopify"],
        "update_inventory": ["squarespace", "shopify"],
        "fulfill_orders": ["squarespace", "shopify"],
        "sync_products": ["squarespace", "shopify"],
        "configure_dns": ["godaddy"],
        "check_health": ["godaddy", "squarespace", "shopify"],
        "query": ["squarespace", "shopify"],
    }
    
    @classmethod
    def resolve(cls, action: str, available_platforms: List[str]) -> List[str]:
        """Get which platforms can handle this action."""
        capable = cls.CAPABILITIES.get(action, [])
        return [p for p in capable if p in available_platforms]
    
    @classmethod
    def get_capabilities(cls, platform: str) -> List[str]:
        """Get capabilities for a platform."""
        return [
            action for action, platforms in cls.CAPABILITIES.items()
            if platform in platforms
        ]


# Executor instance
_executor: Optional[RateLimitedExecutor] = None


def get_executor() -> RateLimitedExecutor:
    """Get global executor instance."""
    global _executor
    if _executor is None:
        _executor = RateLimitedExecutor()
    return _executor