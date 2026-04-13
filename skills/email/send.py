"""Email sending skills for Lipaira.

Provides skills for sending and drafting emails:
- EmailSendSkill: Sends emails via Resend API using Lipaira's API key
- EmailDraftSkill: Generates email content from templates

Key functions/classes:
    EmailSendSkill: Sends emails with optional HTML/text body via Resend
    EmailDraftSkill: Creates email drafts from templates with variable substitution
"""

import requests
from skills.registry import BaseSkill
from skills.base import get_integration_tokens


class EmailSendSkill(BaseSkill):
    """Send an email via Resend.
    
    This skill uses Lipaira's Resend API key, not user's OAuth.
    
    Params:
        to: Email address or list of addresses
        subject: Email subject line
        html: HTML body content
        text: Plain text fallback
        from_email: Sender (defaults to noreply@lipaira.ai)
    
    Returns:
        sent: True if successful
        message_id: Resend message ID
        to: Recipients
        subject: Email subject
    """
    name = "email_send"
    description = "Send an email to a recipient"
    required_integrations = []  # Uses Lipaira's Resend, not user's OAuth
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        # No external integrations needed
        return {"can_run": True, "missing": [], "message": "Ready"}
    
    def execute(self, params: dict, user_id: str, 
                business_id: str = None) -> dict:
        from providers import get_secret
        
        api_key = get_secret("RESEND_API_KEY")
        if not api_key:
            raise ValueError("Resend API not configured")
        
        to = params.get("to", [])
        if isinstance(to, str):
            to = [to]
        
        if not to:
            raise ValueError("'to' parameter is required")
        
        payload = {
            "from": params.get("from", "Lipaira <noreply@lipaira.ai>"),
            "to": to,
            "subject": params.get("subject", ""),
        }
        
        if params.get("html"):
            payload["html"] = params["html"]
        if params.get("text"):
            payload["text"] = params["text"]
        
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )
        
        if response.status_code >= 400:
            raise ValueError(f"Resend error: {response.text}")
        
        result = response.json()
        
        return {
            "sent": True,
            "message_id": result.get("id"),
            "to": to,
            "subject": params.get("subject")
        }


class EmailDraftSkill(BaseSkill):
    """Generate an email draft from a template.
    
    This creates email content - doesn't send it.
    Use email_send to actually deliver.
    
    Params:
        template: Template name (e.g., 'invoice_chase', 'quote_followup')
        context: Dict with template variables (customer_name, amount, etc.)
        tone: 'friendly', 'professional', 'urgent'
    
    Returns:
        subject: Generated subject line
        html: Generated HTML body
        text: Generated plain text body
    """
    name = "email_draft"
    description = "Generate an email from a template"
    required_integrations = []
    
    TEMPLATES = {
        "invoice_chase": {
            "subject": "Friendly reminder: Invoice #{{invoice_number}}",
            "friendly": """
                <p>Hi {{customer_name}},</p>
                <p>Just a friendly reminder that invoice #{{invoice_number}} 
                for ${{amount}} is now {{days_overdue}} days past due.</p>
                <p>If you've already sent payment, please ignore this! 
                Otherwise, let me know if you have any questions.</p>
                <p>Thanks!<br>{{business_name}}</p>
            """,
            "professional": """
                <p>Dear {{customer_name}},</p>
                <p>This is a reminder that invoice #{{invoice_number}} 
                in the amount of ${{amount}} was due on {{due_date}}.</p>
                <p>Please remit payment at your earliest convenience.</p>
                <p>Thank you for your business.</p>
                <p>Sincerely,<br>{{business_name}}</p>
            """,
            "urgent": """
                <p>Dear {{customer_name}},</p>
                <p>Invoice #{{invoice_number}} for ${{amount}} is 
                {{days_overdue}} days overdue.</p>
                <p>Please contact us immediately to avoid further action.</p>
                <p>Regards,<br>{{business_name}}</p>
            """
        },
        "quote_followup": {
            "subject": "Following up on your quote - {{business_name}}",
            "friendly": """
                <p>Hi {{customer_name}},</p>
                <p>I wanted to follow up on the quote I sent for {{project_name}}.</p>
                <p>Happy to answer any questions or make adjustments!</p>
                <p>Best,<br>{{business_name}}</p>
            """,
            "professional": """
                <p>Dear {{customer_name}},</p>
                <p>Following up on our quote for {{project_name}} dated {{quote_date}}.</p>
                <p>Please let us know if you have any questions.</p>
                <p>Regards,<br>{{business_name}}</p>
            """,
            "urgent": """
                <p>Dear {{customer_name}},</p>
                <p>This is a final follow-up on quote #{{quote_number}} 
                for {{project_name}}.</p>
                <p>This quote expires on {{expiry_date}}.</p>
                <p>Regards,<br>{{business_name}}</p>
            """
        }
    }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        return {"can_run": True, "missing": [], "message": "Ready"}
    
    def execute(self, params: dict, user_id: str,
                business_id: str = None) -> dict:
        template_name = params.get("template")
        if not template_name:
            raise ValueError("'template' parameter is required")
        
        if template_name not in self.TEMPLATES:
            raise ValueError(
                f"Unknown template: {template_name}. "
                f"Available: {list(self.TEMPLATES.keys())}"
            )
        
        template = self.TEMPLATES[template_name]
        tone = params.get("tone", "friendly")
        context = params.get("context", {})
        
        # Default values for missing context
        context.setdefault("customer_name", "Customer")
        context.setdefault("business_name", "Your Business")
        
        # Simple template substitution
        def substitute(text):
            result = text
            for key, value in context.items():
                result = result.replace(f"{{{{{key}}}}}", str(value))
            return result
        
        subject = substitute(template["subject"])
        body_template = template.get(tone, template["friendly"])
        html = substitute(body_template)
        
        # Strip HTML for text version
        import re
        text = re.sub('<[^<]+?>', '', html)
        text = re.sub('\n\n+', '\n\n', text)
        
        return {
            "subject": subject,
            "html": html,
            "text": text,
            "template": template_name,
            "tone": tone
        }