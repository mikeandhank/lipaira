"""GitHub integration skill - wraps lipaira-client version."""
from skills.registry import BaseSkill
from lipaira_client.skills.github_skill import GitHubSkill as _GitHubSkill


class GitHubSkill(BaseSkill):
    """Interact with GitHub - create issues, PRs, check status."""
    name = "github"
    description = "Interact with GitHub - create issues, PRs, check status"
    required_integrations = []  # Uses GITHUB_TOKEN from env
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["create_issue", "list_issues", "create_pr"]},
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "title": {"type": "string"},
                "body": {"type": "string"},
                "labels": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["action", "owner", "repo"]
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        return {"can_run": True, "missing": [], "message": "Ready"}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _GitHubSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


__all__ = ['GitHubSkill']