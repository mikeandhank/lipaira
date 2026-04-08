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
        from security.content_wrapper import wrap_external_content
        
        skill = _WebFetchSkill()
        result = skill.execute(input)
        
        # Wrap external content to prevent indirect prompt injection
        if result.success and result.output:
            url = input.get('url', 'unknown')
            try:
                wrapped = wrap_external_content(str(result.output), url, "webpage")
                return {
                    "success": True,
                    "output": wrapped,
                    "url": url
                }
            except ValueError as e:
                logger.error(f"Content wrapper failed for {url}: {e}")
                return {"success": False, "error": str(e)}
            except Exception as e:
                logger.error(f"Content wrapper error: {e}")
                # Return unwrapped on error to not break functionality
                return {
                    "success": result.success,
                    "output": result.output,
                    "error": result.error
                }
        
        return {
            "success": result.success,
            "output": result.output,
            "error": result.error
        }

__all__ = ['WebFetchSkill']