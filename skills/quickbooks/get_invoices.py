"""QuickBooks invoice retrieval skill for Lipaira.

Provides skill for fetching unpaid invoices from QuickBooks.
Uses QuickBooks OAuth tokens fetched from the database.

Key functions/classes:
    QuickBooksGetInvoicesSkill: Fetches overdue invoices with client names, amounts, and days overdue
"""

import requests
from datetime import datetime, timedelta
from skills.registry import BaseSkill
from skills.base import get_integration_tokens


class QuickBooksGetInvoicesSkill(BaseSkill):
    """Get unpaid invoices from QuickBooks.
    
    Required integrations: quickbooks
    
    Params:
        days_overdue: Filter by days overdue (default 7)
        status: Filter by status - 'overdue', 'unpaid', 'all'
    
    Returns:
        success: Whether the call succeeded
        invoices: List of invoice dicts
        count: Number of invoices
        total_outstanding: Sum of all overdue amounts
    """
    execution_tier = "free"  # Read-only: free tier allowed
    
    name = "quickbooks_get_invoices"
    description = (
        "Get unpaid invoices from QuickBooks. "
        "Returns list of invoices with client name, "
        "amount, due date, and days overdue."
    )
    required_integrations = ["quickbooks"]
    
    def execute(self, params: dict, user_id: str,
                business_id: str = None) -> dict:
        tokens = get_integration_tokens(user_id, business_id, "quickbooks")
        
        days_overdue = params.get("days_overdue", 7)
        due_before = (
            datetime.now() - timedelta(days=days_overdue)
        ).strftime('%Y-%m-%d')
        
        # QB API call using sandbox (default)
        query = (
            f"SELECT * FROM Invoice "
            f"WHERE Balance > '0' "
            f"AND DueDate < '{due_before}' "
            f"ORDER BY DueDate ASC MAXRESULTS 50"
        )
        
        realm_id = tokens.get('metadata', {}).get('realm_id')
        if not realm_id:
            # Try to get from extra/metadata field
            realm_id = tokens.get('metadata', {}).get('realmId')
        
        if not realm_id:
            return {
                "success": False,
                "error": "No QuickBooks realm_id found. Reconnect QB.",
                "invoices": []
            }
        
        access_token = tokens['access_token']
        
        # Use sandbox URL for testing
        base_url = "https://sandbox-quickbooks.api.intuit.com"
        
        resp = requests.get(
            f"{base_url}/v3/company/{realm_id}/query",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            },
            params={"query": query},
            timeout=15
        )
        
        if not resp.ok:
            return {
                "success": False,
                "error": f"QB API error: {resp.status_code} - {resp.text[:200]}",
                "invoices": []
            }
        
        data = resp.json()
        invoices = data.get("QueryResponse", {}).get("Invoice", [])
        
        result = []
        for inv in invoices:
            due_date = inv.get("DueDate", "")
            if due_date:
                try:
                    due_dt = datetime.strptime(due_date, "%Y-%m-%d")
                    days_late = (datetime.now() - due_dt).days
                except:
                    days_late = 0
            else:
                days_late = 0
            
            result.append({
                "id": inv.get("Id"),
                "doc_number": inv.get("DocNumber"),
                "client_name": inv.get("CustomerRef", {}).get("name"),
                "client_id": inv.get("CustomerRef", {}).get("value"),
                "amount": float(inv.get("TotalAmt", 0)),
                "balance": float(inv.get("Balance", 0)),
                "due_date": due_date,
                "days_overdue": days_late,
                "status": inv.get("EmailStatus")
            })
        
        return {
            "success": True,
            "invoices": result,
            "count": len(result),
            "total_outstanding": sum(i["balance"] for i in result)
        }

