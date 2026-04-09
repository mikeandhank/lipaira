"""
Web search skill - wraps lipaira-client version.
"""
from skills.registry import BaseSkill
from lipaira_client.skills.web_search import WebSearchSkill as _WebSearchSkill

class WebSearchSkill(BaseSkill):
    """Web search using Brave Search API."""
    name = "web_search"
    description = "Search the web for current information using Brave Search API"
    required_integrations = []  # Uses BRAVE_SEARCH_API_KEY env var
    execution_tier = "free"  # Read-only: free tier allowed
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "default": 5}
            },
            "required": ["query"]
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        return {"can_run": True, "missing": [], "message": "Ready"}
    
    def execute(self, input: dict, user_id: str) -> dict:
        # Delegate to lipaira-client implementation
        skill = _WebSearchSkill()
        result = skill.execute(input)
        return {
            "success": result.success,
            "output": result.output,
            "error": result.error
        }

__all__ = ['WebSearchSkill']