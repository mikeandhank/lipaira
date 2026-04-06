import os
import requests
from .base import BaseSkill, SkillResult

class EmailSendSkill(BaseSkill):
    name = "email_send"
    description = (
        "Send a professional email via Resend API. "
        "Use when asked to send an invoice, follow-up, or any email to a client."
    )
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email"},
                "subject": {"type": "string", "description": "Email subject"},
                "body": {"type": "string", "description": "Email body (HTML or text)"},
                "from_name": {"type": "string", "description": "Sender name"},
                "reply_to": {"type": "string", "description": "Reply-to email"}
            },
            "required": ["to", "subject", "body"]
        }

    def execute(self, input: dict) -> SkillResult:
        api_key = os.environ.get("RESEND_API_KEY")
        
        if not api_key:
            return SkillResult(success=False, output=None, 
                error="Email not configured - RESEND_API_KEY missing")
        
        # Get from env or use default
        from_email = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")
        from_name = input.get("from_name", os.environ.get("RESEND_FROM_NAME", "Lipaira"))
        
        try:
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": f"{from_name} <{from_email}>",
                    "to": [input.get("to")],
                    "subject": input.get("subject"),
                    "html": input.get("body"),
                    "reply_to": input.get("reply_to")
                },
                timeout=30
            )
            
            if response.status_code in (200, 201):
                return SkillResult(success=True, output={
                    "message": f"Email sent to {input.get('to')}",
                    "email_id": response.json().get("id")
                })
            else:
                return SkillResult(success=False, output=None,
                    error=f"Resend error: {response.status_code} - {response.text}")
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))
