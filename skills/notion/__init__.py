"""Notion skills - search and create pages."""

import json
import logging
import requests
from skills.registry import BaseSkill
from skills.base import get_integration_tokens

log = logging.getLogger(__name__)


class NotionSearchSkill(BaseSkill):
    """Search Notion pages and databases.
    
    Uses user's Notion OAuth token to search their workspace.
    
    Params:
        query: Search query string
        limit: Max results (default: 10)
    
    Returns:
        pages: List of matching pages
        databases: List of matching databases
        count: Total results
    """
    name = "notion_search"
    description = "Search Notion for pages and databases"
    required_integrations = ["notion"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "default": 10, "description": "Max results"}
            },
            "required": ["query"]
        }
    
    def execute(self, params, user_id, business_id=None):
        # Handle params parsing
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except:
                params = {}
        elif not params:
            params = {}
        
        try:
            tokens = get_integration_tokens(user_id, business_id, "notion")
            access_token = tokens.get('access_token')
            
            if not access_token:
                return {"pages": [], "databases": [], "count": 0, "error": "Notion not connected"}
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }
            
            query = params.get('query', '')
            limit = params.get('limit', 10)
            
            # Search
            response = requests.post(
                "https://api.notion.com/v1/search",
                headers=headers,
                json={
                    "query": query,
                    "page_size": limit,
                    "filter": {"value": "page", "property": "object"}
                },
                timeout=30
            )
            
            if response.status_code != 200:
                return {"pages": [], "databases": [], "count": 0, "error": response.text}
            
            results = response.json().get("results", [])
            
            pages = []
            for p in results:
                title = "Untitled"
                props = p.get("properties", {})
                if "title" in props and props["title"].get("title"):
                    title = props["title"]["title"][0].get("plain_text", "Untitled")
                elif "Name" in props and props["Name"].get("title"):
                    title = props["Name"]["title"][0].get("plain_text", "Untitled")
                
                pages.append({
                    "id": p["id"],
                    "title": title,
                    "url": p.get("url", ""),
                    "last_edited": p.get("last_edited_time", "")
                })
            
            return {"pages": pages, "databases": [], "count": len(pages)}
            
        except Exception as e:
            log.error(f"Notion search error: {e}")
            return {"pages": [], "databases": [], "count": 0, "error": str(e)}


class NotionCreatePageSkill(BaseSkill):
    """Create a new page in Notion.
    
    Creates a page in a specified database or as a child of a page.
    
    Params:
        title: Page title
        content: Page content (optional, plain text)
        database_id: Parent database ID (optional)
        parent_page_id: Parent page ID (optional)
    
    Returns:
        created: True if successful
        page_id: New page ID
        url: Notion page URL
    """
    name = "notion_create_page"
    description = "Create a new page in Notion"
    required_integrations = ["notion"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Page title"},
                "content": {"type": "string", "description": "Page content (optional)"},
                "database_id": {"type": "string", "description": "Database ID for database page"},
                "parent_page_id": {"type": "string", "description": "Parent page ID"}
            },
            "required": ["title"]
        }
    
    def execute(self, params, user_id, business_id=None):
        # Handle params parsing
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except:
                params = {}
        elif not params:
            params = {}
        
        try:
            tokens = get_integration_tokens(user_id, business_id, "notion")
            access_token = tokens.get('access_token')
            
            if not access_token:
                return {"created": False, "error": "Notion not connected"}
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }
            
            title = params.get("title", "Untitled")
            content = params.get("content", "")
            database_id = params.get("database_id")
            parent_page_id = params.get("parent_page_id")
            
            # Build the page creation payload
            if database_id:
                # Creating in a database
                payload = {
                    "parent": {"database_id": database_id},
                    "properties": {
                        "Name": {
                            "title": [{"text": {"content": title}}]
                        }
                    }
                }
            elif parent_page_id:
                # Creating as child of page
                payload = {
                    "parent": {"page_id": parent_page_id},
                    "properties": {
                        "title": {
                            "title": [{"text": {"content": title}}]
                        }
                    }
                }
            else:
                # Default: create as root page
                payload = {
                    "parent": {"type": "page"},
                    "properties": {
                        "title": {
                            "title": [{"text": {"content": title}}]
                        }
                    }
                }
            
            # Add content if provided
            if content:
                payload["children"] = [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"text": {"content": content}}]
                        }
                    }
                ]
            
            response = requests.post(
                "https://api.notion.com/v1/pages",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code != 200:
                return {"created": False, "error": response.text}
            
            result = response.json()
            
            return {
                "created": True,
                "page_id": result.get("id"),
                "url": result.get("url", ""),
                "title": title
            }
            
        except Exception as e:
            log.error(f"Notion create page error: {e}")
            return {"created": False, "error": str(e)}