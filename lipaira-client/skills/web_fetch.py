import httpx
from urllib.parse import urlparse
from .base import BaseSkill, SkillResult

BLOCKED_HOSTS = [
    "169.254.169.254", # AWS metadata
    "localhost", "127.0.0.1", "0.0.0.0",
    "10.", "192.168.", "172.16.", "172.17.",
]

class WebFetchSkill(BaseSkill):
    name = "web_fetch"
    description = "Fetch and read the content of a public webpage URL."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
                "max_chars": {"type": "integer", "default": 5000}
            },
            "required": ["url"]
        }

    def execute(self, input: dict) -> SkillResult:
        url = input.get("url", "")
        max_chars = min(input.get("max_chars", 5000), 20000)

        parsed = urlparse(url)
        for blocked in BLOCKED_HOSTS:
            if blocked in (parsed.hostname or ""):
                return SkillResult(success=False, output=None,
                    error="URL not permitted")
        if parsed.scheme not in ("http", "https"):
            return SkillResult(success=False, output=None,
                error="Only http/https URLs allowed")
        
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True,
                max_redirects=3) as client:
                response = client.get(url, headers={"User-Agent": "Lipaira/1.0"})
                return SkillResult(success=True, output=response.text[:max_chars])
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))
