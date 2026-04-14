"""Gmail reading skills via Google OAuth."""

import json
import logging
from skills.registry import BaseSkill
from skills.base import get_integration_tokens

log = logging.getLogger(__name__)


class GmailReadSkill(BaseSkill):
    """Read emails from Gmail.
    
    Uses user's Google OAuth tokens to access Gmail.
    
    Params:
        max_results: Maximum number of emails to return (default: 10)
        query: Gmail search query (e.g., "is:unread", "from:xyz@example.com")
        subject: Filter by subject line contains
        from_addr: Filter by sender address
    
    Returns:
        emails: List of email objects with id, subject, from, date, snippet
        count: Number of emails returned
    """
    name = "gmail_read"
    description = "Read emails from Gmail inbox"
    required_integrations = ["google"]
    execution_tier = "free"  # Read-only: free tier allowed
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "default": 10, "description": "Max emails to return"},
                "query": {"type": "string", "description": "Gmail search query (e.g., 'is:unread')"},
                "subject": {"type": "string", "description": "Filter by subject contains"},
                "from_addr": {"type": "string", "description": "Filter by sender"}
            }
        }
    
    def execute(self, params, user_id, business_id=None):
        try:
            # Handle params - could be dict or JSON string from LLM
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except:
                    params = {}
            elif not params:
                params = {}
            
            tokens = get_integration_tokens(user_id, business_id, "gmail")
            log.warning(f"Gmail tokens: access_token={bool(tokens.get('access_token'))}")
            
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            
            # Handle metadata
            metadata = tokens.get('metadata', {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
            
            creds = Credentials(
                token=tokens['access_token'],
                refresh_token=tokens.get('refresh_token'),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=metadata.get('client_id'),
                client_secret=metadata.get('client_secret'),
                scopes=metadata.get('scopes', '').split() if metadata.get('scopes') else []
            )
            
            service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
            
            # Build query
            query = params.get('query', '')
            if params.get('subject'):
                subject_filter = f'subject:{params["subject"]}'
                query = f"{query} {subject_filter}" if query else subject_filter
            if params.get('from_addr'):
                from_filter = f'from:{params["from_addr"]}'
                query = f"{query} {from_filter}" if query else from_filter
            
            max_results = params.get('max_results', 10)
            
            # Get message list
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                return {"emails": [], "count": 0, "message": "No emails found"}
            
            # Get full message details
            emails = []
            for msg in messages[:max_results]:
                msg_data = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['Subject', 'From', 'Date', 'Snippet']
                ).execute()
                
                headers = msg_data.get('payload', {}).get('headers', [])
                header_dict = {h['name'].lower(): h['value'] for h in headers}
                
                emails.append({
                    "id": msg_data['id'],
                    "subject": header_dict.get('subject', '(No subject)'),
                    "from": header_dict.get('from', 'Unknown'),
                    "date": header_dict.get('date', ''),
                    "snippet": msg_data.get('snippet', '')[:200],
                    "thread_id": msg_data.get('threadId')
                })
            
            return {"emails": emails, "count": len(emails)}
            
        except Exception as e:
            import traceback
            log.error(f"Gmail read error: {e} {traceback.format_exc()}")
            return {"emails": [], "count": 0, "error": str(e)}


class GmailSendSkill(BaseSkill):
    """Send an email via Gmail.
    
    Uses user's Google OAuth to send from their Gmail.
    
    Params:
        to: Recipient email address
        subject: Email subject
        body: Email body (plain text)
        html: HTML body (optional)
    
    Returns:
        sent: True if successful
        message_id: Gmail message ID
    """
    name = "gmail_send"
    description = "Send an email via Gmail"
    required_integrations = ["google"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject"},
                "body": {"type": "string", "description": "Plain text body"},
                "html": {"type": "string", "description": "HTML body (optional)"}
            },
            "required": ["to", "subject", "body"]
        }
    
    def execute(self, params, user_id, business_id=None):
        try:
            # Handle params - could be dict or JSON string from LLM
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except:
                    params = {}
            elif not params:
                params = {}
            
            tokens = get_integration_tokens(user_id, business_id, "gmail")
            
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            import base64
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # Handle metadata
            metadata = tokens.get('metadata', {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
            
            creds = Credentials(
                token=tokens['access_token'],
                refresh_token=tokens.get('refresh_token'),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=metadata.get('client_id'),
                client_secret=metadata.get('client_secret'),
                scopes=metadata.get('scopes', '').split() if metadata.get('scopes') else []
            )
            
            service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
            
            # Get user's email address
            profile = service.users().getProfile(userId='me').execute()
            from_email = profile.get('emailAddress')
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = params.get('subject', '')
            msg['From'] = from_email
            msg['To'] = params.get('to', '')
            
            # Add plain text
            if params.get('body'):
                msg.attach(MIMEText(params['body'], 'plain'))
            
            # Add HTML
            if params.get('html'):
                msg.attach(MIMEText(params['html'], 'html'))
            
            # Encode and send
            encoded_msg = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            
            sent = service.users().messages().send(
                userId='me',
                body={'raw': encoded_msg}
            ).execute()
            
            return {
                "sent": True,
                "message_id": sent.get('id'),
                "from": from_email,
                "to": params.get('to')
            }
            
        except Exception as e:
            import traceback
            log.error(f"Gmail send error: {e} {traceback.format_exc()}")
            return {"sent": False, "error": str(e)}