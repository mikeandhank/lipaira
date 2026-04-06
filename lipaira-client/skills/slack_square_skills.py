"""Slack and Square skills."""
import os
import requests
from .base import BaseSkill, SkillResult

GATEWAY_URL = os.environ.get('GATEWAY_URL', 'http://lipaira-api:8080')
SLACK_BASE = "https://slack.com/api"
SQUARE_BASE = "https://connect.squareup.com/v2"

# Slack skills
class SlackPostSkill(BaseSkill):
    name = "slack_post"
    description = "Post a message to a Slack channel."

    def get_input_schema(self):
        return {"type": "object", "properties": {"channel": {"type": "string"}, "message": {"type": "string"}}, "required": ["channel", "message"]}

    def execute(self, input: dict) -> SkillResult:
        try:
            resp = requests.get(f"{GATEWAY_URL}/api/internal/slack-token", timeout=10)
            if resp.status_code == 404:
                return SkillResult(success=False, output=None, error="Slack not connected")
            token = resp.json().get('token')
            
            resp = requests.post(f"{SLACK_BASE}/chat.postMessage",
                                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                                json={"channel": input['channel'], "text": input['message']}).json()
            
            if not resp.get("ok"):
                return SkillResult(success=False, output=None, error=resp.get("error"))
            
            return SkillResult(success=True, output={"ts": resp.get("ts"), "message": f"Posted to {input['channel']}"})
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class SlackReadChannelSkill(BaseSkill):
    name = "slack_read_channel"
    description = "Read recent messages from a Slack channel."

    def get_input_schema(self):
        return {"type": "object", "properties": {"channel": {"type": "string"}, "max_results": {"type": "integer", "default": 20}}, "required": ["channel"]}

    def execute(self, input: dict) -> SkillResult:
        try:
            resp = requests.get(f"{GATEWAY_URL}/api/internal/slack-token", timeout=10)
            if resp.status_code == 404:
                return SkillResult(success=False, output=None, error="Slack not connected")
            token = resp.json().get('token')
            
            # Get channel ID
            channels = requests.get(f"{SLACK_BASE}/conversations.list",
                                   headers={"Authorization": f"Bearer {token}"},
                                   params={"types": "public_channel,private_channel"}).json()
            
            channel_id = None
            channel_name = input["channel"].lstrip("#")
            for ch in channels.get("channels", []):
                if ch.get("name") == channel_name:
                    channel_id = ch["id"]
                    break
            
            if not channel_id:
                return SkillResult(success=False, output=None, error=f"Channel #{channel_name} not found")
            
            history = requests.get(f"{SLACK_BASE}/conversations.history",
                                  headers={"Authorization": f"Bearer {token}"},
                                  params={"channel": channel_id, "limit": input.get("max_results", 20)}).json()
            
            messages = [{"user": msg.get("user", ""), "text": msg.get("text", ""), "ts": msg.get("ts", "")} 
                       for msg in history.get("messages", [])]
            return SkillResult(success=True, output=messages)
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


# Square skills
class SquareInvoiceCreateSkill(BaseSkill):
    name = "square_invoice_create"
    description = "Create and send a Square invoice."

    def get_input_schema(self):
        return {"type": "object", "properties": {"customer_name": {"type": "string"}, "customer_email": {"type": "string"}, "amount": {"type": "number"}, "description": {"type": "string"}}, 
                "required": ["customer_name", "customer_email", "amount"]}

    def execute(self, input: dict) -> SkillResult:
        try:
            resp = requests.get(f"{GATEWAY_URL}/api/internal/square-token", timeout=10)
            if resp.status_code == 404:
                return SkillResult(success=False, output=None, error="Square not connected")
            token = resp.json().get('token')
            
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Square-Version": "2024-01-18"}
            
            # Get location
            locations = requests.get(f"{SQUARE_BASE}/locations", headers=headers).json()
            location_id = locations.get("locations", [{}])[0].get("id")
            if not location_id:
                return SkillResult(success=False, output=None, error="No Square location found")
            
            # Search customer
            cust_search = requests.post(f"{SQUARE_BASE}/customers/search", headers=headers,
                                       json={"query": {"filter": {"email_address": {"exact": input["customer_email"]}}}}).json()
            
            customer_id = None
            if cust_search.get("customers"):
                customer_id = cust_search["customers"][0]["id"]
            else:
                # Create customer
                name_parts = input["customer_name"].split()
                new_cust = requests.post(f"{SQUARE_BASE}/customers", headers=headers,
                                        json={"given_name": name_parts[0], "family_name": " ".join(name_parts[1:]) if len(name_parts) > 1 else "",
                                             "email_address": input["customer_email"]}).json()
                customer_id = new_cust.get("customer", {}).get("id")
            
            # Create order
            amount_cents = int(float(input["amount"]) * 100)
            import uuid
            order = requests.post(f"{SQUARE_BASE}/orders", headers=headers,
                                 json={"order": {"location_id": location_id, "customer_id": customer_id,
                                                "line_items": [{"quantity": "1", "base_price_money": {"amount": amount_cents, "currency": "USD"},
                                                              "name": input.get("description", "Service")}]},
                                       "idempotency_key": str(uuid.uuid4())}).json()
            
            order_id = order.get("order", {}).get("id")
            if not order_id:
                return SkillResult(success=False, output=None, error="Failed to create order")
            
            from datetime import datetime, timedelta
            due_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            
            # Create invoice
            inv = requests.post(f"{SQUARE_BASE}/invoices", headers=headers,
                               json={"invoice": {"location_id": location_id, "order_id": order_id,
                                                "primary_recipient": {"customer_id": customer_id},
                                                "payment_requests": [{"request_type": "BALANCE", "due_date": due_date}],
                                                "delivery_method": "EMAIL"},
                                      "idempotency_key": str(uuid.uuid4())}).json()
            
            inv_id = inv.get("invoice", {}).get("id")
            
            # Publish
            requests.post(f"{SQUARE_BASE}/invoices/{inv_id}/publish", headers=headers,
                         json={"version": 0, "idempotency_key": str(uuid.uuid4())})
            
            return SkillResult(success=True, output={"invoice_id": inv_id, "amount": f"${input['amount']}", "message": f"Invoice sent to {input['customer_email']}"})
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class SquareCustomerLookupSkill(BaseSkill):
    name = "square_customer_lookup"
    description = "Look up a customer in Square."

    def get_input_schema(self):
        return {"type": "object", "properties": {"name": {"type": "string"}, "email": {"type": "string"}}}

    def execute(self, input: dict) -> SkillResult:
        try:
            resp = requests.get(f"{GATEWAY_URL}/api/internal/square-token", timeout=10)
            if resp.status_code == 404:
                return SkillResult(success=False, output=None, error="Square not connected")
            token = resp.json().get('token')
            
            headers = {"Authorization": f"Bearer {token}", "Square-Version": "2024-01-18"}
            
            if input.get("email"):
                data = requests.post(f"{SQUARE_BASE}/customers/search", headers=headers,
                                    json={"query": {"filter": {"email_address": {"exact": input["email"]}}}}).json()
                customers = data.get("customers", [])
            else:
                data = requests.get(f"{SQUARE_BASE}/customers", headers=headers).json()
                customers = data.get("customers", [])
                if input.get("name"):
                    name_lower = input["name"].lower()
                    customers = [c for c in customers if name_lower in f"{c.get('given_name','')} {c.get('family_name','')}".lower()]
            
            output = [{"id": c.get("id"), "name": f"{c.get('given_name','')} {c.get('family_name','')}".strip(),
                      "email": c.get("email_address", "")} for c in customers[:10]]
            return SkillResult(success=True, output=output)
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))