"""Google Calendar skills - real implementation."""

import datetime
import json
import logging
from skills.registry import BaseSkill
from skills.base import get_integration_tokens

log = logging.getLogger(__name__)


class CalendarGetEventsSkill(BaseSkill):
    """Get calendar events from Google Calendar."""
    name = "calendar_get_events"
    description = "Get upcoming calendar events from Google Calendar."
    execution_tier = "free"  # Read-only: free tier allowed
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "default": 7, "description": "How many days ahead to look"},
                "max_events": {"type": "integer", "default": 10, "description": "Maximum events to return"}
            }
        }
    
    def execute(self, params, user_id, business_id=None):
        try:
            # Handle params - could be dict or JSON string from LLM
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except:
                    params = {}
            elif not params:
                params = {}
            
            tokens = get_integration_tokens(user_id, business_id, "google_calendar")
            log.warning(f"Calendar tokens: access_token={bool(tokens.get('access_token'))}")
            
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            
            # Handle metadata - could be dict or need parsing
            metadata = tokens.get('metadata', {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
            
            creds = Credentials(
                token=tokens['access_token'],
                refresh_token=tokens.get('refresh_token'),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=metadata.get('client_id'),
                client_secret=metadata.get('client_secret'),
                scopes=metadata.get('scopes', '').split() if metadata.get('scopes') else []
            )
            
            service = build('calendar', 'v3', credentials=creds, cache_discovery=False)
            
            now = datetime.datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            time_max = (now + datetime.timedelta(days=params.get('days_ahead', 7))).isoformat() + 'Z'
            
            events_result = service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                maxResults=params.get('max_events', 10),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            if not events:
                return {"events": [], "count": 0, "message": "No upcoming events found"}
            
            formatted = []
            for e in events:
                start = e['start'].get('dateTime', e['start'].get('date', 'TBD'))
                end = e['end'].get('dateTime', e['end'].get('date', 'TBD'))
                formatted.append({
                    "id": e['id'],
                    "title": e.get('summary', '(No title)'),
                    "start": start,
                    "end": end,
                    "location": e.get('location', ''),
                    "description": e.get('description', '')[:200] if e.get('description') else ''
                })
            
            return {"events": formatted, "count": len(formatted)}
            
        except Exception as e:
            import traceback
            log.error(f"Calendar error: {e} {traceback.format_exc()}")
            return {"events": [], "count": 0, "error": str(e)}