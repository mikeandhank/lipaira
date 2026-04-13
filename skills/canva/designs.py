"""Canva integration skills for Lipaira.

Provides skills for interacting with Canva's REST API.
Each skill fetches OAuth tokens from the database and uses them to
authenticate requests to Canva's API.

Key functions/classes:
    CanvaGetDesignsSkill: Fetches recent designs with titles, IDs, and URLs
    CanvaCreateDesignSkill: Creates new designs with type and title
"""

import requests
from skills.registry import BaseSkill
from skills.base import get_integration_tokens


class CanvaGetDesignsSkill(BaseSkill):
    name = "canva_get_designs"
    description = (
        "Get recent Canva designs. Use to find marketing "
        "materials, flyers, social posts, or business graphics."
    )
    required_integrations = ["canva"]
    
    def execute(self, params, user_id, business_id=None):
        tokens = get_integration_tokens(user_id, business_id, "canva")
        if not tokens:
            return {"success": False, "error": "Canva not connected"}
        
        try:
            resp = requests.get(
                "https://api.canva.com/rest/v1/designs",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                params={"limit": params.get("limit", 10)}
            )
            if resp.ok:
                designs = resp.json().get("items", [])
                return {
                    "success": True,
                    "designs": [{
                        "id": d["id"],
                        "title": d.get("title", "Untitled"),
                        "edit_url": d.get("urls", {}).get("edit_url"),
                        "view_url": d.get("urls", {}).get("view_url")
                    } for d in designs]
                }
            return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}


class CanvaCreateDesignSkill(BaseSkill):
    name = "canva_create_design"
    description = (
        "Create a new Canva design. "
        "Use for flyers, social media posts, "
        "or marketing materials."
    )
    required_integrations = ["canva"]
    
    def execute(self, params, user_id, business_id=None):
        tokens = get_integration_tokens(user_id, business_id, "canva")
        if not tokens:
            return {"success": False, "error": "Canva not connected"}
        
        try:
            resp = requests.post(
                "https://api.canva.com/rest/v1/designs",
                headers={
                    "Authorization": f"Bearer {tokens['access_token']}",
                    "Content-Type": "application/json"
                },
                json={
                    "design_type": {"type": params.get("design_type", "flyer")},
                    "title": params.get("title", "New Design")
                }
            )
            if resp.ok:
                d = resp.json().get("design", {})
                return {
                    "success": True,
                    "design_id": d.get("id"),
                    "edit_url": d.get("urls", {}).get("edit_url")
                }
            return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}