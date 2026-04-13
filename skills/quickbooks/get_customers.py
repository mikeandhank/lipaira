"""QuickBooks integration skills for Lipaira.

Provides skills for interacting with QuickBooks.
Uses QuickBooks OAuth tokens fetched from the database.

Key functions/classes:
    QuickBooksGetCustomersSkill: Lists customers from QuickBooks (placeholder - not implemented)
    QuickBooksGetInvoicesSkill: Fetches overdue invoices with client names, amounts, and due dates
"""

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