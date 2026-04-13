"""Square integration skills for Lipaira.

Provides skills for interacting with Square APIs:
- SquareInvoiceCreateSkill: Create invoices in Square
- SquareCustomerLookupSkill: Search for customers in Square
- SquareAppointmentListSkill: List upcoming appointments

Key functions/classes:
    SquareInvoiceCreateSkill: Creates new Square invoices
    SquareCustomerLookupSkill: Searches Square customers
    SquareAppointmentListSkill: Lists Square appointments
"""
from skills.registry import BaseSkill
from lipaira_client.skills.square_skills import (
    SquareInvoiceCreateSkill as _SquareInvoiceCreateSkill,
    SquareCustomerLookupSkill as _SquareCustomerLookupSkill,
    SquareAppointmentListSkill as _SquareAppointmentListSkill
)


class SquareInvoiceCreateSkill(BaseSkill):
    """Create a Square invoice."""
    name = "square_invoice_create"
    description = "Create a new invoice in Square"
    required_integrations = ["square"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "amount": {"type": "number"},
                "currency": {"type": "string", "default": "USD"},
                "due_date": {"type": "string", "description": "YYYY-MM-DD"},
                "line_items": {"type": "array"}
            },
            "required": ["customer_id", "amount"]
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        from skills.base import get_integration_tokens
        try:
            get_integration_tokens(user_id, business_id, 'square')
            return {"can_run": True, "missing": [], "message": "Ready"}
        except ValueError as e:
            return {"can_run": False, "missing": ["square"], "message": str(e)}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _SquareInvoiceCreateSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


class SquareCustomerLookupSkill(BaseSkill):
    """Look up Square customers."""
    name = "square_customer_lookup"
    description = "Search for customers in Square"
    required_integrations = ["square"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "default": 10}
            },
            "required": ["query"]
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        from skills.base import get_integration_tokens
        try:
            get_integration_tokens(user_id, business_id, 'square')
            return {"can_run": True, "missing": [], "message": "Ready"}
        except ValueError as e:
            return {"can_run": False, "missing": ["square"], "message": str(e)}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _SquareCustomerLookupSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


class SquareAppointmentListSkill(BaseSkill):
    """List Square appointments."""
    name = "square_appointment_list"
    description = "List upcoming appointments from Square"
    required_integrations = ["square"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20}
            }
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        from skills.base import get_integration_tokens
        try:
            get_integration_tokens(user_id, business_id, 'square')
            return {"can_run": True, "missing": [], "message": "Ready"}
        except ValueError as e:
            return {"can_run": False, "missing": ["square"], "message": str(e)}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _SquareAppointmentListSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


__all__ = ['SquareInvoiceCreateSkill', 'SquareCustomerLookupSkill', 'SquareAppointmentListSkill']