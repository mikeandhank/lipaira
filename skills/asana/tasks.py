"""Asana integration skills for Lipaira.

Provides skills for interacting with Asana workspaces via the Asana API.
Each skill fetches OAuth tokens from the database and uses them to
authenticate requests to Asana's REST API.

Key functions/classes:
    AsanaGetTasksSkill: Fetches incomplete tasks assigned to the authenticated user
    AsanaCreateTaskSkill: Creates new tasks in the user's primary Asana workspace
"""

import requests
from skills.registry import BaseSkill
from skills.base import get_integration_tokens


class AsanaGetTasksSkill(BaseSkill):
    name = "asana_get_tasks"
    description = (
        "Get tasks from Asana. Returns task names, "
        "due dates, and completion status. "
        "Use for project briefings and deadline tracking."
    )
    required_integrations = ["asana"]
    
    def execute(self, params, user_id, business_id=None):
        tokens = get_integration_tokens(user_id, business_id, "asana")
        if not tokens:
            return {"success": False, "error": "Asana not connected"}
        
        try:
            headers = {"Authorization": f"Bearer {tokens['access_token']}"}
            
            # Get user's workspaces
            me = requests.get("https://app.asana.com/api/1.0/users/me", headers=headers).json()
            workspaces = me.get("data", {}).get("workspaces", [])
            
            if not workspaces:
                return {"success": False, "error": "No Asana workspace found"}
            
            workspace_id = workspaces[0]["gid"]
            
            # Get tasks
            resp = requests.get(
                "https://app.asana.com/api/1.0/tasks",
                headers=headers,
                params={
                    "workspace": workspace_id,
                    "assignee": "me",
                    "completed": False,
                    "opt_fields": "name,due_on,completed,notes"
                }
            )
            
            if resp.ok:
                return {"success": True, "tasks": resp.json().get("data", [])[:20]}
            return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}


class AsanaCreateTaskSkill(BaseSkill):
    name = "asana_create_task"
    description = (
        "Create a task in Asana. "
        "Use for action items, project tasks, or follow-ups."
    )
    required_integrations = ["asana"]
    
    def execute(self, params, user_id, business_id=None):
        tokens = get_integration_tokens(user_id, business_id, "asana")
        if not tokens:
            return {"success": False, "error": "Asana not connected"}
        
        try:
            headers = {
                "Authorization": f"Bearer {tokens['access_token']}",
                "Content-Type": "application/json"
            }
            
            # Get user's workspace
            me = requests.get("https://app.asana.com/api/1.0/users/me", headers=headers).json()
            workspaces = me.get("data", {}).get("workspaces", [])
            
            if not workspaces:
                return {"success": False, "error": "No Asana workspace found"}
            
            workspace_id = workspaces[0]["gid"]
            
            # Create task
            resp = requests.post(
                "https://app.asana.com/api/1.0/tasks",
                headers=headers,
                json={"data": {
                    "name": params.get("name"),
                    "notes": params.get("description", ""),
                    "due_on": params.get("due_date"),
                    "assignee": "me",
                    "workspace": workspace_id
                }}
            )
            
            if resp.ok:
                task = resp.json().get("data", {})
                return {"success": True, "task_id": task["gid"], "name": task.get("name")}
            return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}