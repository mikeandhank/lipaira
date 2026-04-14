import os
import httpx
from .base import BaseSkill, SkillResult

class WebSearchSkill(BaseSkill):
    name = "web_search"
    description = "Search the web for current information, news, and facts."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "default": 5}
            },
            "required": ["query"]
        }

    def execute(self, input: dict) -> SkillResult:
        query = input.get("query", "")
        max_results = min(input.get("max_results", 5), 10)
        api_key = os.environ.get("BRAVE_SEARCH_API_KEY")

        if not api_key:
            return SkillResult(success=False, output=None,
                error="Search not configured — BRAVE_SEARCH_API_KEY missing")
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={"X-Subscription-Token": api_key,
                    "Accept": "application/json"},
                    params={"q": query, "count": max_results}
                )
                response.raise_for_status()
                results = response.json().get("web", {}).get("results", [])
                return SkillResult(success=True, output=[{
                    "title": r.get("title"),
                    "url": r.get("url"),
                    "description": r.get("description")
                } for r in results])
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))
