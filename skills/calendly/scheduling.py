"""Calendly integration skills for Lipaira.

Provides skills for interacting with Calendly's scheduling API.
Each skill fetches OAuth tokens from the database and uses them to
authenticate requests to Calendly's REST API.

Key functions/classes:
    CalendlyGetScheduledEventsSkill: Fetches active/confirmed upcoming events
    CalendlyGetEventTypesSkill: Retrieves event types with booking URLs
"""

import requests
from skills.registry import BaseSkill
from skills.base import get_integration_tokens


class CalendlyGetScheduledEventsSkill(BaseSkill):
    name = "calendly_get_scheduled_events"
    description = (
        "Get upcoming scheduled events from Calendly. "
        "Use to see booked appointments and client meetings."
    )
    required_integrations = ["calendly"]
    
    def execute(self, params, user_id, business_id=None):
        tokens = get_integration_tokens(user_id, business_id, "calendly")
        if not tokens:
            return {"success": False, "error": "Calendly not connected"}
        
        try:
            me = requests.get(
                "https://api.calendly.com/users/me",
                headers={"Authorization": f"Bearer {tokens['access_token']}"}
            ).json()
            
            if "resource" not in me:
                return {"success": False, "error": "Could not get Calendly user"}
            
            user_uri = me["resource"]["uri"]
            resp = requests.get(
                "https://api.calendly.com/scheduled_events",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                params={
                    "user": user_uri,
                    "status": "active",
                    "sort": "start_time:asc",
                    "count": params.get("limit", 10)
                }
            )
            if resp.ok:
                events = resp.json().get("collection", [])
                return {
                    "success": True,
                    "events": [{
                        "name": e.get("name"),
                        "start_time": e.get("start_time"),
                        "end_time": e.get("end_time"),
                        "join_url": e.get("location", {}).get("join_url", "")
                    } for e in events]
                }
            return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}


class CalendlyGetEventTypesSkill(BaseSkill):
    name = "calendly_get_event_types"
    description = (
        "Get Calendly booking links and event types. "
        "Use to share booking links with clients."
    )
    required_integrations = ["calendly"]
    
    def execute(self, params, user_id, business_id=None):
        tokens = get_integration_tokens(user_id, business_id, "calendly")
        if not tokens:
            return {"success": False, "error": "Calendly not connected"}
        
        try:
            me = requests.get(
                "https://api.calendly.com/users/me",
                headers={"Authorization": f"Bearer {tokens['access_token']}"}
            ).json()
            
            if "resource" not in me:
                return {"success": False, "error": "Could not get Calendly user"}
            
            user_uri = me["resource"]["uri"]
            resp = requests.get(
                "https://api.calendly.com/event_types",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                params={"user": user_uri, "active": True}
            )
            if resp.ok:
                types = resp.json().get("collection", [])
                return {
                    "success": True,
                    "event_types": [{
                        "name": t.get("name"),
                        "duration": t.get("duration"),
                        "booking_url": t.get("scheduling_url")
                    } for t in types]
                }
            return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}