"""
Microsoft Graph integration skills - wraps lipaira-client version.
"""
from skills.registry import BaseSkill
from lipaira_client.skills.microsoft_skills import (
    OutlookSendSkill as _OutlookSendSkill,
    OutlookReadSkill as _OutlookReadSkill,
    OutlookCalendarReadSkill as _OutlookCalendarReadSkill,
    OutlookCalendarWriteSkill as _OutlookCalendarWriteSkill,
    OneDriveUploadSkill as _OneDriveUploadSkill,
    WordCreateSkill as _WordCreateSkill,
    ExcelCreateSkill as _ExcelCreateSkill,
    OneNoteCreateSkill as _OneNoteCreateSkill,
    OutlookContactLookupSkill as _OutlookContactLookupSkill
)


class OutlookSendSkill(BaseSkill):
    """Send an email from the user's Outlook/Microsoft account."""
    name = "outlook_send"
    description = "Send an email from the user's Outlook/Microsoft account"
    required_integrations = ["microsoft"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "cc": {"type": "string"}
            },
            "required": ["to", "subject", "body"]
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        from skills.base import get_integration_tokens
        try:
            get_integration_tokens(user_id, business_id, 'microsoft')
            return {"can_run": True, "missing": [], "message": "Ready"}
        except ValueError as e:
            return {"can_run": False, "missing": ["microsoft"], "message": str(e)}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _OutlookSendSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


class OutlookReadSkill(BaseSkill):
    """Read recent emails from the user's Outlook inbox."""
    name = "outlook_read"
    description = "Read recent emails from the user's Outlook inbox"
    required_integrations = ["microsoft"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "default": 5},
                "unread_only": {"type": "boolean", "default": False}
            }
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        from skills.base import get_integration_tokens
        try:
            get_integration_tokens(user_id, business_id, 'microsoft')
            return {"can_run": True, "missing": [], "message": "Ready"}
        except ValueError as e:
            return {"can_run": False, "missing": ["microsoft"], "message": str(e)}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _OutlookReadSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


class OutlookCalendarReadSkill(BaseSkill):
    """Read upcoming events from the user's Outlook Calendar."""
    name = "outlook_calendar_read"
    description = "Read upcoming events from the user's Outlook Calendar"
    required_integrations = ["microsoft"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "default": 7},
                "max_results": {"type": "integer", "default": 10}
            }
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        from skills.base import get_integration_tokens
        try:
            get_integration_tokens(user_id, business_id, 'microsoft')
            return {"can_run": True, "missing": [], "message": "Ready"}
        except ValueError as e:
            return {"can_run": False, "missing": ["microsoft"], "message": str(e)}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _OutlookCalendarReadSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


class OutlookCalendarWriteSkill(BaseSkill):
    """Create a calendar event in the user's Outlook Calendar."""
    name = "outlook_calendar_write"
    description = "Create a calendar event in the user's Outlook Calendar"
    required_integrations = ["microsoft"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start": {"type": "string", "description": "ISO 8601"},
                "end": {"type": "string"},
                "description": {"type": "string"},
                "location": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string"}},
                "add_teams": {"type": "boolean", "default": False}
            },
            "required": ["title", "start", "end"]
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        from skills.base import get_integration_tokens
        try:
            get_integration_tokens(user_id, business_id, 'microsoft')
            return {"can_run": True, "missing": [], "message": "Ready"}
        except ValueError as e:
            return {"can_run": False, "missing": ["microsoft"], "message": str(e)}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _OutlookCalendarWriteSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


class OneDriveUploadSkill(BaseSkill):
    """Upload a file from documents to OneDrive."""
    name = "onedrive_upload"
    description = "Upload a file from documents to OneDrive"
    required_integrations = ["microsoft"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "folder": {"type": "string", "default": "Lipaira Documents"}
            },
            "required": ["filename"]
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        from skills.base import get_integration_tokens
        try:
            get_integration_tokens(user_id, business_id, 'microsoft')
            return {"can_run": True, "missing": [], "message": "Ready"}
        except ValueError as e:
            return {"can_run": False, "missing": ["microsoft"], "message": str(e)}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _OneDriveUploadSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


class WordCreateSkill(BaseSkill):
    """Create a Word document in OneDrive."""
    name = "word_create"
    description = "Create a Word document in OneDrive"
    required_integrations = ["microsoft"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "folder": {"type": "string", "default": "Lipaira Documents"}
            },
            "required": ["title", "content"]
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        from skills.base import get_integration_tokens
        try:
            get_integration_tokens(user_id, business_id, 'microsoft')
            return {"can_run": True, "missing": [], "message": "Ready"}
        except ValueError as e:
            return {"can_run": False, "missing": ["microsoft"], "message": str(e)}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _WordCreateSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


class ExcelCreateSkill(BaseSkill):
    """Create an Excel spreadsheet in OneDrive."""
    name = "excel_create"
    description = "Create an Excel spreadsheet in OneDrive"
    required_integrations = ["microsoft"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "headers": {"type": "array", "items": {"type": "string"}},
                "rows": {"type": "array", "items": {"type": "array"}},
                "folder": {"type": "string", "default": "Lipaira Documents"}
            },
            "required": ["title", "headers"]
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        from skills.base import get_integration_tokens
        try:
            get_integration_tokens(user_id, business_id, 'microsoft')
            return {"can_run": True, "missing": [], "message": "Ready"}
        except ValueError as e:
            return {"can_run": False, "missing": ["microsoft"], "message": str(e)}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _ExcelCreateSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


class OneNoteCreateSkill(BaseSkill):
    """Create a OneNote page with content."""
    name = "onenote_create"
    description = "Create a OneNote page with content"
    required_integrations = ["microsoft"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "section_name": {"type": "string", "default": "Lipaira"}
            },
            "required": ["title", "content"]
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        from skills.base import get_integration_tokens
        try:
            get_integration_tokens(user_id, business_id, 'microsoft')
            return {"can_run": True, "missing": [], "message": "Ready"}
        except ValueError as e:
            return {"can_run": False, "missing": ["microsoft"], "message": str(e)}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _OneNoteCreateSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


class OutlookContactLookupSkill(BaseSkill):
    """Look up a contact from Outlook Contacts by name."""
    name = "outlook_contact_lookup"
    description = "Look up a contact from Outlook Contacts by name"
    required_integrations = ["microsoft"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        from skills.base import get_integration_tokens
        try:
            get_integration_tokens(user_id, business_id, 'microsoft')
            return {"can_run": True, "missing": [], "message": "Ready"}
        except ValueError as e:
            return {"can_run": False, "missing": ["microsoft"], "message": str(e)}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _OutlookContactLookupSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


__all__ = [
    'OutlookSendSkill',
    'OutlookReadSkill',
    'OutlookCalendarReadSkill',
    'OutlookCalendarWriteSkill',
    'OneDriveUploadSkill',
    'WordCreateSkill',
    'ExcelCreateSkill',
    'OneNoteCreateSkill',
    'OutlookContactLookupSkill'
]