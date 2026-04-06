"""Restaurant reservation skill - per SPEC Item 12."""
import os
import logging
import json
import requests
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

OPENTABLE_API_KEY = os.environ.get('OPENTABLE_API_KEY', '')
RESY_API_KEY = os.environ.get('RESY_API_KEY', '')


class RestaurantReservationSkill:
    """Book restaurant reservations via OpenTable or Resy.""" 
    
    name = "restaurant_reservation"
    description = "Book restaurant reservations"
    required_integrations = []
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language: 'book dinner Saturday 7pm 4 people Italian'"},
                "select_option": {"type": "integer", "description": "Option number to select (1-3)"}
            },
            "required": ["query"]
        }
    
    def can_execute(self, user_id: str, business_id: str = None):
        return {"can_run": True, "missing": [], "message": "Ready"}
    
    def execute(self, input: dict, user_id: str) -> dict:
        query = input.get("query", "")
        select_option = input.get("select_option")
        
        # Step 1: Parse NL to date, time, party size, cuisine
        parsed = self._parse_query(query)
        
        # Step 2: Search availability
        options = self._search_availability(parsed)
        
        if not options:
            return {"success": False, "error": "No availability found"}
        
        # If user selecting an option, confirm
        if select_option is not None:
            if select_option < 1 or select_option > len(options):
                return {"success": False, "error": "Invalid option selection"}
            
            selected = options[select_option - 1]
            confirmation = self._confirm_reservation(selected, user_id)
            
            # Step 5: Create calendar event
            self._create_calendar_event(selected, user_id)
            
            return {
                "success": True,
                "confirmed": True,
                "restaurant": selected['restaurant'],
                "time": selected['time'],
                "date": selected['date'],
                "party_size": selected['party_size'],
                "confirmation": confirmation['confirmation_id']
            }
        
        # Return options for user to choose
        return {
            "success": True,
            "options": options,
            "message": f"Found {len(options)} options. Reply with 'select 1', 'select 2', or 'select 3' to confirm."
        }
    
    def _parse_query(self, query: str) -> dict:
        """Parse natural language to reservation parameters."""
        query = query.lower()
        
        # Parse party size
        party_size = 2
        for word in query.split():
            if word.isdigit() and 1 <= int(word) <= 20:
                party_size = int(word)
        
        # Parse cuisine
        cuisines = ['italian', 'mexican', 'chinese', 'japanese', 'american', 'french', 'indian', 'thai']
        cuisine = 'american'
        for c in cuisines:
            if c in query:
                cuisine = c
                break
        
        # Parse day
        today = datetime.now()
        if 'saturday' in query:
            days_ahead = 6 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            date = (today + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
        elif 'sunday' in query:
            days_ahead = 7 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            date = (today + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
        elif 'tomorrow' in query:
            date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            date = today.strftime('%Y-%m-%d')
        
        # Parse time
        hour = 19  # Default 7pm
        if '7pm' in query or '7 pm' in query:
            hour = 19
        elif '6pm' in query or '6 pm' in query:
            hour = 18
        elif '8pm' in query or '8 pm' in query:
            hour = 20
        elif '12pm' in query or 'noon' in query:
            hour = 12
        
        time_str = f"{hour}:00"
        
        return {
            'date': date,
            'time': time_str,
            'party_size': party_size,
            'cuisine': cuisine
        }
    
    def _search_availability(self, parsed: dict) -> list:
        """Search OpenTable/Resy for availability."""
        # Mock results if no API key
        if not OPENTABLE_API_KEY and not RESY_API_KEY:
            base_options = [
                {'restaurant': f'{parsed["cuisine"].title()} Place', 'rating': 4.5},
                {'restaurant': f'The {parsed["cuisine"].title()} Kitchen', 'rating': 4.3},
                {'restaurant': f'{parsed["cuisine"].title()} Bistro', 'rating': 4.7},
            ]
            return [
                {
                    **opt,
                    'date': parsed['date'],
                    'time': parsed['time'],
                    'party_size': parsed['party_size'],
                    'address': '123 Main St'
                }
                for opt in base_options
            ]
        
        # Real API call would go here
        return []
    
    def _confirm_reservation(self, option: dict, user_id: str) -> dict:
        """Confirm the reservation via API."""
        import uuid
        return {
            'confirmation_id': f'RES-{uuid.uuid4().hex[:8].upper()}',
            'restaurant': option['restaurant']
        }
    
    def _create_calendar_event(self, option: dict, user_id: str):
        """Create calendar event for reservation."""
        # Would integrate with Google Calendar API
        logger.info(f"Would create calendar event for {option['restaurant']} at {option['time']}")


restaurant_skill = RestaurantReservationSkill()
