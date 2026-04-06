"""QuickBooks customer skills."""

from skills.registry import BaseSkill
from skills.base import get_integration_tokens


class QuickBooksGetCustomersSkill(BaseSkill):
    """Get customers from QuickBooks."""
    name = "quickbooks_get_customers"
    description = "List customers from QuickBooks"
    required_integrations = ["quickbooks"]
    
    def execute(self, params, user_id, business_id=None):
        tokens = get_integration_tokens(user_id, business_id, "quickbooks")
        return {"customers": [], "count": 0, "note": "Not implemented"}