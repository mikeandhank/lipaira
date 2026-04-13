"""
Google Calendar skill - read and write calendar events.

Exports:
- CalendarReadSkill: List upcoming events from Google Calendar
- CalendarWriteSkill: Create calendar events with attendees

Both skills use the shared google_client.build_service() helper
to obtain a pre-authenticated Google Calendar API service.
"""
import datetime
from .base import BaseSkill, SkillResult
from .google_client import build_service


class CalendarReadSkill(BaseSkill):
    name = "calendar_read"
    description = "Read upcoming calendar events from Google Calendar."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "default": 7, "description": "How many days ahead to look"},
                "max_events": {"type": "integer", "default": 10, "description": "Maximum events to return"}
            }
        }
    
    def execute(self, input: dict) -> SkillResult:
        try:
            service = build_service('calendar', 'v3')
            
            now = datetime.datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            time_max = (now + datetime.timedelta(days=input.get('days_ahead', 7))).isoformat() + 'Z'
            
            events_result = service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                maxResults=input.get('max_events', 10),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            if not events:
                return SkillResult(
                    success=True,
                    output={"events": [], "message": "No upcoming events found"}
                )
            
            formatted = []
            for e in events:
                start = e['start'].get('dateTime', e['start'].get('date', 'TBD'))
                end = e['end'].get('dateTime', e['end'].get('date', 'TBD'))
                formatted.append({
                    "id": e['id'],
                    "title": e['summary'],
                    "start": start,
                    "end": end,
                    "attendees": [a.get('email', '') for a in e.get('attendees', [])],
                    "location": e.get('location', ''),
                    "description": e.get('description', '')[:200]
                })
            
            return SkillResult(
                success=True,
                output={"events": formatted, "count": len(formatted)}
            )
            
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class CalendarWriteSkill(BaseSkill):
    name = "calendar_write"
    description = "Create a calendar event. Returns the created event details."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Event title"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "time": {"type": "string", "description": "HH:MM (24-hour format)"},
                "duration_minutes": {"type": "integer", "default": 60},
                "attendees": {"type": "array", "items": {"type": "string"}, "description": "Email addresses"},
                "description": {"type": "string", "description": "Event description"},
                "location": {"type": "string", "description": "Location/address"}
            },
            "required": ["title", "date"]
        }
    
    def execute(self, input: dict) -> SkillResult:
        try:
            service = build_service('calendar', 'v3')
            
            # Build start/end datetime
            date = input['date']
            time = input.get('time', '09:00')
            duration = input.get('duration_minutes', 60)
            
            start_dt = datetime.datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            end_dt = start_dt + datetime.timedelta(minutes=duration)
            
            event = {
                'summary': input['title'],
                'description': input.get('description', ''),
                'location': input.get('location', ''),
                'start': {
                    'dateTime': start_dt.isoformat(),
                    'timeZone': 'America/New_York',
                },
                'end': {
                    'dateTime': end_dt.isoformat(),
                    'timeZone': 'America/New_York',
                },
            }
            
            attendees = input.get('attendees', [])
            if attendees:
                event['attendees'] = [{'email': a} for a in attendees]
            
            created = service.events().insert(
                calendarId='primary',
                body=event,
                sendUpdates='none'
            ).execute()
            
            return SkillResult(
                success=True,
                output={
                    "event_id": created['id'],
                    "link": created.get('htmlLink', ''),
                    "title": created['summary'],
                    "start": created['start']['dateTime'],
                    "message": "Event created successfully"
                }
            )
            
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))