"""Trello skills for Lipaira.

Provides skills for interacting with Trello boards using OAuth 1.0a.
Note: Trello uses OAuth 1.0a (different from OAuth 2.0 used by most other providers).

Key functions/classes:
    TrelloGetCardsSkill: Fetches cards from a board with name, description, due date
    TrelloCreateCardSkill: Creates new cards in a specified Trello list
"""

import requests
from skills.registry import BaseSkill
from skills.base import get_integration_tokens


class TrelloGetCardsSkill(BaseSkill):
    name = "trello_get_cards"
    description = (
        "Get cards from Trello boards. "
        "Use for job tracking, project status, and task management."
    )
    required_integrations = ["trello"]
    
    def execute(self, params, user_id, business_id=None):
        tokens = get_integration_tokens(user_id, business_id, "trello")
        if not tokens:
            return {"success": False, "error": "Trello not connected"}
        
        try:
            api_key = tokens.get("metadata", {}).get("api_key")
            api_token = tokens.get("access_token")
            
            if not api_key or not api_token:
                return {"success": False, "error": "Trello credentials incomplete"}
            
            # Get board ID from params or fetch first board
            board_id = params.get("board_id")
            if not board_id:
                boards = requests.get(
                    "https://api.trello.com/1/members/me/boards",
                    params={"key": api_key, "token": api_token, "filter": "open"}
                ).json()
                
                if not boards:
                    return {"success": False, "error": "No boards found"}
                board_id = boards[0]["id"]
            
            # Get cards
            resp = requests.get(
                f"https://api.trello.com/1/boards/{board_id}/cards",
                params={
                    "key": api_key,
                    "token": api_token,
                    "fields": "name,desc,due,dueComplete,url"
                }
            )
            
            if resp.ok:
                return {"success": True, "cards": resp.json()[:20]}
            return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}


class TrelloCreateCardSkill(BaseSkill):
    name = "trello_create_card"
    description = (
        "Create a new card in Trello. "
        "Use to add jobs, tasks, or follow-ups."
    )
    required_integrations = ["trello"]
    
    def execute(self, params, user_id, business_id=None):
        tokens = get_integration_tokens(user_id, business_id, "trello")
        if not tokens:
            return {"success": False, "error": "Trello not connected"}
        
        try:
            api_key = tokens.get("metadata", {}).get("api_key")
            api_token = tokens.get("access_token")
            
            if not api_key or not api_token:
                return {"success": False, "error": "Trello credentials incomplete"}
            
            list_id = params.get("list_id")
            if not list_id:
                return {"success": False, "error": "list_id required"}
            
            resp = requests.post(
                "https://api.trello.com/1/cards",
                params={"key": api_key, "token": api_token},
                json={
                    "idList": list_id,
                    "name": params.get("name"),
                    "desc": params.get("description", ""),
                    "due": params.get("due_date")
                }
            )
            
            if resp.ok:
                card = resp.json()
                return {"success": True, "card_id": card["id"], "url": card["url"]}
            return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}