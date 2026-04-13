"""
Project management integration skills for Lipaira.
Supports Notion, Trello, Asana, Monday, and Basecamp via unified
BaseSkill interface. Each platform has dedicated classes for listing
and creating tasks, cards, and projects. Routes through GATEWAY_URL.
"""
import os
import requests
from .base import BaseSkill, SkillResult

GATEWAY_URL = os.environ.get('GATEWAY_URL', 'http://lipaira-api:80')
USER_ID = os.environ.get('USER_ID', 'default')


def pm_post(provider: str, endpoint: str, body: dict) -> dict:
    resp = requests.post(
        f'{GATEWAY_URL}/api/pm/{provider}{endpoint}',
        headers={'X-User-ID': USER_ID, 'Content-Type': 'application/json'},
        json=body, timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def pm_get(provider: str, endpoint: str, params: dict = None) -> dict:
    resp = requests.get(
        f'{GATEWAY_URL}/api/pm/{provider}{endpoint}',
        headers={'X-User-ID': USER_ID},
        params=params, timeout=30
    )
    resp.raise_for_status()
    return resp.json()


class NotionCreatePageSkill:
    name = "notion_page_create"
    description = "Create a new page in Notion."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["title"]
        }
    
    def execute(self, input: dict):
        from .base import SkillResult
        try:
            import os
            NOTION_KEY = os.environ.get('NOTION_API_KEY')
            if not NOTION_KEY:
                return SkillResult(success=False, output=None, error="Notion not connected")
            
            headers = {"Authorization": f"Bearer {NOTION_KEY}", "Notion-Version": "2025-09-03"}
            resp = requests.post(
                "https://api.notion.com/v1/pages",
                headers=headers,
                json={
                    "parent": {"page_id": os.environ.get('NOTION_PARENT_PAGE', "")},
                    "properties": {"title": {"title": [{"text": {"content": input['title']}}]}}
                },
                timeout=30
            )
            if resp.status_code != 200:
                return SkillResult(success=False, output=None, error=resp.text[:200])
            
            data = resp.json()
            return SkillResult(success=True, output={
                "page_id": data.get("id"),
                "url": f"https://notion.so/{data.get('id').replace('-', '')}",
                "message": f"Notion page '{input['title']}' created"
            })
        except Exception as e:
            from .base import SkillResult
            return SkillResult(success=False, output=None, error=str(e))


class NotionSearchSkill:
    name = "notion_search"
    description = "Search Notion for pages."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
    
    def execute(self, input: dict):
        from .base import SkillResult
        try:
            import os
            NOTION_KEY = os.environ.get('NOTION_API_KEY')
            if not NOTION_KEY:
                return SkillResult(success=False, output=None, error="Notion not connected")
            
            headers = {"Authorization": f"Bearer {NOTION_KEY}", "Notion-Version": "2025-09-03"}
            resp = requests.post(
                "https://api.notion.com/v1/search",
                headers=headers,
                json={"query": input['query'], "page_size": 5},
                timeout=30
            )
            results = resp.json().get("results", [])
            return SkillResult(success=True, output=[
                {"title": r.get("properties", {}).get("title", {}).get("title", [{}])[0].get("plain_text", "Untitled"),
                 "id": r.get("id")} for r in results[:5]
            ])
        except Exception as e:
            from .base import SkillResult
            return SkillResult(success=False, output=None, error=str(e))


class TrelloCardCreateSkill:
    name = "trello_card_create"
    description = "Create a card on a Trello board."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "board": {"type": "string"},
                "list": {"type": "string", "default": "To Do"}
            },
            "required": ["title", "board"]
        }
    
    def execute(self, input: dict):
        from .base import SkillResult
        try:
            import os
            token = os.environ.get('TRELLO_TOKEN')
            key = os.environ.get('TRELLO_API_KEY')
            if not token or not key:
                return SkillResult(success=False, output=None, error="Trello not connected")
            
            # Get board ID
            resp = requests.get(
                f"https://api.trello.com/1/members/me/boards",
                params={"key": key, "token": token},
                timeout=30
            )
            boards = resp.json()
            board_id = None
            for b in boards:
                if input.get("board", "").lower() in b.get("name", "").lower():
                    board_id = b.get("id")
                    break
            
            if not board_id:
                return SkillResult(success=False, output=None, error=f"Board '{input['board']}' not found")
            
            # Get lists
            resp = requests.get(
                f"https://api.trello.com/1/boards/{board_id}/lists",
                params={"key": key, "token": token},
                timeout=30
            )
            lists = resp.json()
            list_id = lists[0].get("id") if lists else None
            
            if not list_id:
                return SkillResult(success=False, output=None, error="No lists found on board")
            
            # Create card
            resp = requests.post(
                f"https://api.trello.com/1/cards",
                params={"key": key, "token": token, "idList": list_id, "name": input['title']},
                timeout=30
            )
            card = resp.json()
            return SkillResult(success=True, output={
                "card_id": card.get("id"),
                "url": card.get("url"),
                "message": f"Trello card '{input['title']}' created"
            })
        except Exception as e:
            from .base import SkillResult
            return SkillResult(success=False, output=None, error=str(e))


class AsanaTaskCreateSkill:
    name = "asana_task_create"
    description = "Create a task in Asana."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "project": {"type": "string"},
                "due_date": {"type": "string"}
            },
            "required": ["title"]
        }
    
    def execute(self, input: dict):
        from .base import SkillResult
        try:
            import os
            token = os.environ.get('ASANA_TOKEN')
            if not token:
                return SkillResult(success=False, output=None, error="Asana not connected")
            
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            
            # Get projects
            resp = requests.get(
                "https://app.asana.com/api/1.0/projects",
                headers=headers,
                timeout=30
            )
            projects = resp.json().get("data", [])
            project_id = None
            for p in projects:
                if input.get("project", "").lower() in p.get("name", "").lower():
                    project_id = p.get("gid")
                    break
            
            if not project_id and projects:
                project_id = projects[0].get("gid")
            
            if not project_id:
                return SkillResult(success=False, output=None, error="No project found")
            
            # Create task
            data = {"name": input['title'], "projects": [project_id]}
            if input.get("due_date"):
                data["due_on"] = input['due_date']
            
            resp = requests.post(
                "https://app.asana.com/api/1.0/tasks",
                headers=headers,
                json=data,
                timeout=30
            )
            task = resp.json().get("data", {})
            return SkillResult(success=True, output={
                "task_id": task.get("gid"),
                "url": f"https://app.asana.com/0/{task.get('gid')}",
                "message": f"Asana task '{input['title']}' created"
            })
        except Exception as e:
            from .base import SkillResult
            return SkillResult(success=False, output=None, error=str(e))


class MondayItemCreateSkill:
    name = "monday_item_create"
    description = "Create an item on a Monday.com board."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "board": {"type": "string"}
            },
            "required": ["title", "board"]
        }
    
    def execute(self, input: dict):
        from .base import SkillResult
        try:
            import os
            token = os.environ.get('MONDAY_TOKEN')
            if not token:
                return SkillResult(success=False, output=None, error="Monday.com not connected")
            
            headers = {"Authorization": token, "Content-Type": "application/json"}
            
            # Get boards
            resp = requests.post(
                "https://api.monday.com/v2",
                headers=headers,
                json={"query": "{boards { id name } }"},
                timeout=30
            )
            boards = resp.json().get("data", {}).get("boards", [])
            board_id = None
            for b in boards:
                if input.get("board", "").lower() in b.get("name", "").lower():
                    board_id = b.get("id")
                    break
            
            if not board_id and boards:
                board_id = boards[0].get("id")
            
            if not board_id:
                return SkillResult(success=False, output=None, error="No board found")
            
            # Create item
            resp = requests.post(
                "https://api.monday.com/v2",
                headers=headers,
                json={
                    "query": f'mutation {{ create_item (board_id: {board_id}, item_name: "{input["title"]}") {{ id }} }}'
                },
                timeout=30
            )
            item = resp.json().get("data", {}).get("create_item", {})
            return SkillResult(success=True, output={
                "item_id": item.get("id"),
                "message": f"Monday item '{input['title']}' created"
            })
        except Exception as e:
            from .base import SkillResult
            return SkillResult(success=False, output=None, error=str(e))


class BasecampTodoCreateSkill:
    name = "basecamp_todo_create"
    description = "Create a to-do in Basecamp."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "project": {"type": "string"}
            },
            "required": ["title", "project"]
        }
    
    def execute(self, input: dict):
        from .base import SkillResult
        try:
            import os
            account_id = os.environ.get('BASECAMP_ACCOUNT_ID')
            token = os.environ.get('BASECAMP_TOKEN')
            if not token or not account_id:
                return SkillResult(success=False, output=None, error="Basecamp not connected")
            
            # Get projects
            resp = requests.get(
                f"https://basecamp.com/{account_id}/api/v1/projects.json",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=30
            )
            projects = resp.json()
            project_id = None
            for p in projects:
                if input.get("project", "").lower() in p.get("name", "").lower():
                    project_id = p.get("id")
                    break
            
            if not project_id and projects:
                project_id = projects[0].get("id")
            
            if not project_id:
                return SkillResult(success=False, output=None, error="No project found")
            
            # Get todoset
            resp = requests.get(
                f"https://basecamp.com/{account_id}/api/v1/projects/{project_id}/todolists.json",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30
            )
            lists = resp.json()
            list_id = lists[0].get("id") if lists else None
            
            if not list_id:
                return SkillResult(success=False, output=None, error="No todo list found")
            
            # Create todo
            resp = requests.post(
                f"https://basecamp.com/{account_id}/api/v1/todolists/{list_id}/todos.json",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"content": input['title']},
                timeout=30
            )
            todo = resp.json()
            return SkillResult(success=True, output={
                "todo_id": todo.get("id"),
                "message": f"Basecamp todo '{input['title']}' created"
            })
        except Exception as e:
            from .base import SkillResult
            return SkillResult(success=False, output=None, error=str(e))