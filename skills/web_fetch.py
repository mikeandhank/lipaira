"""
Web fetch skill - wraps lipaira-client version with SSRF protection.
"""
from skills.registry import BaseSkill
from lipaira_client.skills.web_fetch import WebFetchSkill as _WebFetchSkill

class WebFetchSkill(BaseSkill):
    """Fetch web page content with SSRF protection."""
    name = "web_fetch"
    description = "Fetch and extract content from web pages with SSRF protection"
    required_integrations = []  # No auth required
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
                "max_chars": {"type": "integer", "default": 10000}
            },
            "required": ["url"]
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        return {"can_run": True, "missing": [], "message": "Ready"}
    
    def execute(self, input: dict, user_id: str) -> dict:
        skill = _WebFetchSkill()
        result = skill.execute(input)
        return {
            "success": result.success,
            "output": result.output,
            "error": result.error
        }

__all__ = ['WebFetchSkill']