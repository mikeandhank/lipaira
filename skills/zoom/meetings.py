"""
Zoom skills for Lipaira.
"""

import requests
from skills.registry import BaseSkill
from skills.base import get_integration_tokens


class ZoomGetMeetingsSkill(BaseSkill):
    name = "zoom_get_meetings"
    description = (
        "Get upcoming Zoom meetings. Use for daily briefings, "
        "meeting prep, and schedule awareness."
    )
    required_integrations = ["zoom"]
    
    def execute(self, params, user_id, business_id=None):
        tokens = get_integration_tokens(user_id, business_id, "zoom")
        if not tokens:
            return {"success": False, "error": "Zoom not connected"}
        
        try:
            resp = requests.get(
                "https://api.zoom.us/v2/users/me/meetings",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                params={"type": "upcoming", "page_size": params.get("limit", 10)}
            )
            if resp.ok:
                meetings = resp.json().get("meetings", [])
                return {
                    "success": True,
                    "meetings": [{
                        "id": m["id"],
                        "topic": m.get("topic"),
                        "start_time": m.get("start_time"),
                        "duration": m.get("duration"),
                        "join_url": m.get("join_url")
                    } for m in meetings]
                }
            return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}


class ZoomCreateMeetingSkill(BaseSkill):
    name = "zoom_create_meeting"
    description = (
        "Create a Zoom meeting and get the join link. "
        "Use for scheduling client calls, estimates, or consultations."
    )
    required_integrations = ["zoom"]
    
    def execute(self, params, user_id, business_id=None):
        tokens = get_integration_tokens(user_id, business_id, "zoom")
        if not tokens:
            return {"success": False, "error": "Zoom not connected"}
        
        try:
            resp = requests.post(
                "https://api.zoom.us/v2/users/me/meetings",
                headers={
                    "Authorization": f"Bearer {tokens['access_token']}",
                    "Content-Type": "application/json"
                },
                json={
                    "topic": params.get("topic", "Meeting"),
                    "type": 2,
                    "start_time": params.get("start_time"),
                    "duration": params.get("duration", 60),
                    "agenda": params.get("agenda", ""),
                    "settings": {"waiting_room": True, "host_video": True}
                }
            )
            if resp.ok:
                m = resp.json()
                return {
                    "success": True,
                    "join_url": m["join_url"],
                    "topic": m["topic"],
                    "start_time": m["start_time"]
                }
            return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}