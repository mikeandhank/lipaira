"""
GitHub skill - interact with GitHub issues and pull requests.

Exports:
- GitHubSkill: Create issues, list issues, and create PRs
  using the GitHub REST API v3.

Requires GITHUB_TOKEN environment variable for authentication.
"""
import os
import requests
from .base import BaseSkill, SkillResult

class GitHubSkill(BaseSkill):
    name = "github"
    description = "Interact with GitHub - create issues, PRs, check status."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["create_issue", "list_issues", "create_pr"], "default": "list_issues"},
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "title": {"type": "string"},
                "body": {"type": "string"},
                "labels": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["action", "owner", "repo"]
        }
    
    def execute(self, input: dict) -> SkillResult:
        token = os.environ.get("GITHUB_TOKEN")
        
        if not token:
            return SkillResult(success=False, output=None,
                error="GitHub not configured - GITHUB_TOKEN missing")
        
        owner = input.get("owner")
        repo = input.get("repo")
        action = input.get("action")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        try:
            if action == "list_issues":
                response = requests.get(
                    f"https://api.github.com/repos/{owner}/{repo}/issues",
                    headers=headers, timeout=30
                )
                if response.status_code == 200:
                    issues = response.json()[:5]
                    return SkillResult(success=True, output={
                        "issues": [{"title": i["title"], "url": i["html_url"]} for i in issues]
                    })
            
            elif action == "create_issue":
                response = requests.post(
                    f"https://api.github.com/repos/{owner}/{repo}/issues",
                    headers=headers,
                    json={
                        "title": input.get("title", "New Issue"),
                        "body": input.get("body", ""),
                        "labels": input.get("labels", [])
                    },
                    timeout=30
                )
                if response.status_code in (200, 201):
                    return SkillResult(success=True, output={
                        "message": "Issue created",
                        "url": response.json().get("html_url")
                    })
            
            return SkillResult(success=False, output=None,
                error=f"GitHub action '{action}' failed")
                
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))
