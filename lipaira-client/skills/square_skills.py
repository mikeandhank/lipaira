"""
Square skills for invoicing, customers, and appointments.
"""
import os
import requests
from datetime import datetime, timedelta
from .base import BaseSkill, SkillResult

GATEWAY_URL = os.environ.get('GATEWAY_URL', 'http://lipaira-api:80')
USER_ID = os.environ.get('USER_ID', 'default')
SQUARE_BASE = "https://connect.squareup.com/v2"


def get_square_token():
    import os
    return os.environ.get('SQUARE_ACCESS_TOKEN')


def get_square_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Square-Version": "2024-01-18"
    }


class SquareInvoiceCreateSkill:
    name = "square_invoice_create"
    description = "Create and send a Square invoice to a customer."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string"},
                "customer_email": {"type": "string"},
                "line_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "quantity": {"type": "number", "default": 1},
                            "amount": {"type": "number"}
                        }
                    }
                },
                "due_days": {"type": "integer", "default": 30},
                "note": {"type": "string"}
            },
            "required": ["customer_name", "customer_email", "line_items"]
        }
    
    def execute(self, input: dict):
        from .base import SkillResult
        try:
            token = get_square_token()
            if not token:
                return SkillResult(success=False, output=None, error="Square not connected")
            
            headers = get_square_headers(token)
            
            # Find or create customer
            customer_resp = requests.post(
                f"{SQUARE_BASE}/customers/search",
                headers=headers,
                json={"query": {"filter": {"email_address": {"exact": input["customer_email"]}}}},
                timeout=30
            ).json()
            
            customers = customer_resp.get("customers", [])
            if customers:
                customer_id = customers[0]["id"]
            else:
                new_cust = requests.post(
                    f"{SQUARE_BASE}/customers",
                    headers=headers,
                    json={
                        "given_name": input["customer_name"].split()[0],
                        "family_name": " ".join(input["customer_name"].split()[1:]),
                        "email_address": input["customer_email"]
                    },
                    timeout=30
                ).json()
                customer_id = new_cust["customer"]["id"]
            
            # Get location
            locations = requests.get(f"{SQUARE_BASE}/locations", headers=headers, timeout=30).json()
            location_id = locations["locations"][0]["id"]
            
            # Build line items
            line_items = []
            total = 0
            for item in input["line_items"]:
                amount_cents = int(float(item["amount"]) * 100)
                qty = int(item.get("quantity", 1))
                total += amount_cents * qty
                line_items.append({
                    "quantity": str(qty),
                    "base_price_money": {"amount": amount_cents, "currency": "USD"},
                    "name": item["description"]
                })
            
            # Create order
            import uuid
            order = requests.post(
                f"{SQUARE_BASE}/orders",
                headers=headers,
                json={
                    "order": {"location_id": location_id, "customer_id": customer_id, "line_items": line_items},
                    "idempotency_key": str(uuid.uuid4())
                },
                timeout=30
            ).json()
            order_id = order["order"]["id"]
            
            # Create invoice
            due_date = (datetime.now() + timedelta(days=input.get("due_days", 30))).strftime("%Y-%m-%d")
            
            invoice = requests.post(
                f"{SQUARE_BASE}/invoices",
                headers=headers,
                json={
                    "invoice": {
                        "location_id": location_id,
                        "order_id": order_id,
                        "primary_recipient": {"customer_id": customer_id},
                        "payment_requests": [{"request_type": "BALANCE", "due_date": due_date, "automatic_payment_source": "NONE"}],
                        "delivery_method": "EMAIL",
                        "invoice_number": f"INV-{datetime.now().strftime('%Y%m%d')}"
                    },
                    "idempotency_key": str(uuid.uuid4())
                },
                timeout=30
            ).json()
            
            inv_id = invoice["invoice"]["id"]
            
            # Publish
            requests.post(
                f"{SQUARE_BASE}/invoices/{inv_id}/publish",
                headers=headers,
                json={"version": 0, "idempotency_key": str(uuid.uuid4())},
                timeout=30
            )
            
            return SkillResult(success=True, output={
                "invoice_id": inv_id,
                "customer": input["customer_name"],
                "total": f"${total/100:.2f}",
                "due_date": due_date,
                "message": f"Square invoice sent to {input['customer_email']} for ${total/100:.2f}"
            })
        except Exception as e:
            from .base import SkillResult
            return SkillResult(success=False, output=None, error=str(e))


class SquareCustomerLookupSkill:
    name = "square_customer_lookup"
    description = "Look up a customer in Square by name or email."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"}
            }
        }
    
    def execute(self, input: dict):
        from .base import SkillResult
        try:
            token = get_square_token()
            if not token:
                return SkillResult(success=False, output=None, error="Square not connected")
            
            headers = get_square_headers(token)
            
            if input.get("email"):
                data = requests.post(
                    f"{SQUARE_BASE}/customers/search",
                    headers=headers,
                    json={"query": {"filter": {"email_address": {"exact": input["email"]}}}},
                    timeout=30
                ).json()
            else:
                data = requests.get(f"{SQUARE_BASE}/customers", headers=headers, timeout=30).json()
            
            customers = data.get("customers", [])
            if input.get("name"):
                name_lower = input["name"].lower()
                customers = [c for c in customers if name_lower in f"{c.get('given_name','')} {c.get('family_name','')}".lower()]
            
            return SkillResult(success=True, output=[
                {"id": c.get("id"), "name": f"{c.get('given_name','')} {c.get('family_name','')}".strip(),
                 "email": c.get("email_address", ""), "phone": c.get("phone_number", "")}
                for c in customers[:10]
            ])
        except Exception as e:
            from .base import SkillResult
            return SkillResult(success=False, output=None, error=str(e))


class SquareAppointmentListSkill:
    name = "square_appointments_list"
    description = "List upcoming Square appointments."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {"days_ahead": {"type": "integer", "default": 7}}
        }
    
    def execute(self, input: dict):
        from .base import SkillResult
        try:
            from datetime import timezone
            token = get_square_token()
            if not token:
                return SkillResult(success=False, output=None, error="Square not connected")
            
            headers = get_square_headers(token)
            
            locations = requests.get(f"{SQUARE_BASE}/locations", headers=headers, timeout=30).json()
            location_id = locations["locations"][0]["id"]
            
            now = datetime.now(timezone.utc)
            end = now + timedelta(days=input.get("days_ahead", 7))
            
            data = requests.get(
                f"{SQUARE_BASE}/bookings",
                headers=headers,
                params={"location_id": location_id, "start_at_min": now.isoformat(), 
                        "start_at_max": end.isoformat(), "limit": 50},
                timeout=30
            ).json()
            
            return SkillResult(success=True, output=[
                {"id": b.get("id"), "start": b.get("start_at"), "duration": b.get("duration_minutes"),
                 "status": b.get("status"), "customer_id": b.get("customer_id")}
                for b in data.get("bookings", [])
            ])
        except Exception as e:
            from .base import SkillResult
            return SkillResult(success=False, output=None, error=str(e))