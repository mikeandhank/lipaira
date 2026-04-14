import os
import requests
from .base import BaseSkill, SkillResult

class NotionCreatePageSkill(BaseSkill):
    name = "notion_create_page"
    description = "Create a new page in Notion database. Use for CRM, tracking, notes."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "database_id": {"type": "string"},
                "title": {"type": "string"},
                "content": {"type": "string"},
                "properties": {"type": "object"}
            },
            "required": ["title"]
        }
    
    def execute(self, input: dict) -> SkillResult:
        api_key = os.environ.get("NOTION_API_KEY")
        
        if not api_key:
            return SkillResult(success=False, output=None,
                error="Notion not configured - NOTION_API_KEY missing")
        
        # If no database_id provided, create a page
        url = "https://api.notion.com/v1/pages"
        
        properties = {
            "title": {"title": [{"text": {"content": input.get("title", "Untitled")}}]}
        }
        
        # Add any custom properties
        if input.get("properties"):
            properties.update(input["properties"])
        
        try:
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Notion-Version": "2025-09-03",
                    "Content-Type": "application/json"
                },
                json={
                    "parent": {},
                    "properties": properties
                },
                timeout=30
            )
            
            if response.status_code in (200, 201):
                return SkillResult(success=True, output={
                    "message": f"Created page: {input.get('title')}",
                    "page_id": response.json().get("id")
                })
            else:
                return SkillResult(success=False, output=None,
                    error=f"Notion error: {response.status_code}")
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))
