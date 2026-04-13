"""
Intent Parser — natural language to structured intent for Lipaira operator.
Uses the LLM (GPT-4o-mini via unified_api) to parse free-text commands into
OperatorIntent dataclasses with action_type, platform, parameters, risk_level,
and expected_outcome. The primary classification engine for operator commands.
"""
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Supported operator actions."""
    UPDATE_PRICES = "update_prices"
    UPDATE_INVENTORY = "update_inventory"
    FULFILL_ORDERS = "fulfill_orders"
    SYNC_PRODUCTS = "sync_products"
    CONFIGURE_DNS = "configure_dns"
    CHECK_HEALTH = "check_health"
    QUERY = "query"


class RiskLevel(str, Enum):
    """Risk assessment for operations."""
    LOW = "low"       # Read-only, no data modification
    MEDIUM = "medium" # Modifies data, reversible
    HIGH = "high"     # Modifies data, not easily reversible


@dataclass
class OperatorIntent:
    """Structured intent from natural language."""
    action: ActionType
    target: str
    filters: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "action": self.action.value,
            "target": self.target,
            "filters": self.filters,
            "parameters": self.parameters,
            "requires_approval": self.requires_approval
        }


# Prompt for LLM intent parsing
INTENT_SYSTEM_PROMPT = """You are an intent parser for a multi-platform e-commerce operator.

Parse the user's command into a structured JSON intent.

Valid actions:
- update_prices: Modify product prices (increase, decrease, set)
- update_inventory: Modify stock quantities
- fulfill_orders: Mark orders as shipped/fulfilled
- sync_products: Synchronize product data between platforms
- configure_dns: Set up DNS records for a domain
- check_health: Check connection status of integrations
- query: Get information without modifying anything

Return ONLY valid JSON, no explanation. Format:

{
  "action": "update_prices",
  "target": "prices",
  "filters": {"status": "active", "category": "widgets"},
  "parameters": {"increase_by": 0.10},
  "requires_approval": true
}

Examples:
- "Increase all prices by 10%" → {"action": "update_prices", "parameters": {"increase_by": 0.10}, "requires_approval": true}
- "Set all out of stock items to 5 units" → {"action": "update_inventory", "parameters": {"quantity": 5, "only_out_of_stock": true}, "requires_approval": true}
- "Fulfill pending orders" → {"action": "fulfill_orders", "filters": {"status": "pending"}, "requires_approval": true}
- "Sync my products" → {"action": "sync_products", "parameters": {}, "requires_approval": false}
- "Check which integrations are connected" → {"action": "check_health", "target": "integrations", "requires_approval": false}
- "How many orders do I have?" → {"action": "query", "target": "orders", "requires_approval": false}
- "Set up email for davesplumbing.com" → {"action": "configure_dns", "filters": {"domain": "davesplumbing.com"}, "parameters": {"email_provider": "resend.com"}, "requires_approval": true}
"""


class IntentParser:
    """Parses natural language commands into structured intents using LLM."""
    
    def __init__(self):
        self.llm_available = self._check_llm()
    
    def _check_llm(self) -> bool:
        """Check if LLM is available."""
        # Check if we have API access
        try:
            from providers import get_provider
            return True
        except:
            return False
    
    async def parse(self, command: str) -> OperatorIntent:
        """
        Parse a natural language command into an OperatorIntent.
        
        Args:
            command: User's natural language command
            
        Returns:
            OperatorIntent with structured action
            
        If LLM unavailable, falls back to pattern matching.
        """
        if self.llm_available:
            try:
                return await self._parse_with_llm(command)
            except Exception as e:
                logger.warning(f"LLM parse failed, falling back: {e}")
        
        # Fallback to pattern matching
        return self._parse_fallback(command)
    
    async def _parse_with_llm(self, command: str) -> OperatorIntent:
        """Use LLM to parse intent."""
        from providers import get_provider
        
        # Get available model
        try:
            model = get_provider("openrouter").get_model("anthropic/claude-3-haiku")
        except:
            model = None
        
        if not model:
            raise Exception("No LLM available")
        
        # Call LLM
        response = model.chat([
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": command}
        ])
        
        # Parse response
        try:
            data = json.loads(response.content)
        except:
            logger.error(f"Failed to parse LLM response: {response.content}")
            return self._parse_fallback(command)
        
        # Validate and create intent
        action = data.get("action", "query")
        if action not in [a.value for a in ActionType]:
            action = "query"
        
        return OperatorIntent(
            action=ActionType(action),
            target=data.get("target", "unknown"),
            filters=data.get("filters", {}),
            parameters=data.get("parameters", {}),
            requires_approval=data.get("requires_approval", True)
        )
    
    def _parse_fallback(self, command: str) -> OperatorIntent:
        """Fallback pattern matching for intent parsing."""
        command_lower = command.lower()
        
        # Check for various actions
        if "price" in command_lower or "increase" in command_lower or "decrease" in command_lower:
            # Extract percentage if present
            import re
            pct_match = re.search(r'(\d+)%', command)
            increase_by = None
            if pct_match:
                increase_by = int(pct_match.group(1)) / 100
            elif "increase" in command_lower:
                increase_by = 0.10  # Default
            elif "decrease" in command_lower:
                increase_by = -0.10
            
            return OperatorIntent(
                action=ActionType.UPDATE_PRICES,
                target="prices",
                parameters={"increase_by": increase_by} if increase_by else {},
                requires_approval=True
            )
        
        elif "inventory" in command_lower or "stock" in command_lower or "quantity" in command_lower:
            return OperatorIntent(
                action=ActionType.UPDATE_INVENTORY,
                target="inventory",
                requires_approval=True
            )
        
        elif "fulfill" in command_lower or "ship" in command_lower:
            return OperatorIntent(
                action=ActionType.FULFILL_ORDERS,
                target="orders",
                filters={"status": "pending"},
                requires_approval=True
            )
        
        elif "sync" in command_lower:
            return OperatorIntent(
                action=ActionType.SYNC_PRODUCTS,
                target="products",
                requires_approval=False
            )
        
        elif "dns" in command_lower or "email" in command_lower or "domain" in command_lower:
            # Extract domain
            import re
            domain_match = re.search(r'([a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,})', command)
            return OperatorIntent(
                action=ActionType.CONFIGURE_DNS,
                target="dns",
                filters={"domain": domain_match.group(1) if domain_match else ""},
                requires_approval=True
            )
        
        elif "check" in command_lower or "status" in command_lower or "connected" in command_lower:
            return OperatorIntent(
                action=ActionType.CHECK_HEALTH,
                target="integrations",
                requires_approval=False
            )
        
        elif "how many" in command_lower or "show me" in command_lower or "?" in command:
            return OperatorIntent(
                action=ActionType.QUERY,
                target="unknown",
                requires_approval=False
            )
        
        # Default
        return OperatorIntent(
            action=ActionType.QUERY,
            target="unknown",
            requires_approval=False
        )
    
    def assess_risk(self, intent: OperatorIntent) -> RiskLevel:
        """Assess risk level of an intent."""
        if not intent.requires_approval:
            return RiskLevel.LOW
        
        # Read-only actions are low risk
        if intent.action in [ActionType.CHECK_HEALTH, ActionType.QUERY]:
            return RiskLevel.LOW
        
        # Sync is medium (can be re-done)
        if intent.action == ActionType.SYNC_PRODUCTS:
            return RiskLevel.MEDIUM
        
        # Modifications are high
        return RiskLevel.HIGH


# Global instance
_intent_parser: Optional[IntentParser] = None


def get_intent_parser() -> IntentParser:
    """Get global intent parser instance."""
    global _intent_parser
    if _intent_parser is None:
        _intent_parser = IntentParser()
    return _intent_parser