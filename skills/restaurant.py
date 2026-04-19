"""Restaurant reservation skill - per SPEC Item 12."""
import os
import logging
import json
import requests
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import time

logger = logging.getLogger(__name__)

OPENTABLE_API_KEY = os.getenv('OPENTABLE_API_KEY', '')
RESY_API_KEY = os.getenv('RESY_API_KEY', '')

class RestaurantReservationSkill:
    """Book restaurant reservations via OpenTable or Resy.""" 
    
    name = "restaurant_reservation"
    description = "Book restaurant reservations"
    required_integrations = []
    
    def __init__(self):
        self.opentable_base_url = "https://opentable-api.example.com"  # Placeholder
        self.resy_base_url = "https://api.resy.com"
    
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
        if not os.getenv("OPENTABLE_API_KEY") and not os.getenv("RESY_API_KEY"):
            return {"can_run": False, "reason": "No restaurant integration configured. Connect OpenTable or Resy in Settings."}
        return {"can_run": True}
    
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
            
            if not confirmation.get("success"):
                return {"success": False, "error": confirmation.get("error", "Reservation failed")}
            
            # Step 5: Create calendar event
            self._create_calendar_event(selected, user_id)
            
            return {
                "success": True,
                "confirmed": True,
                "restaurant": selected['restaurant'],
                "time": selected['time'],
                "date": selected['date'],
                "party_size": selected['party_size'],
                "confirmation": confirmation.get('confirmation_id', 'N/A')
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
            'cuisine': cuisine,
            'city': 'New York'  # Default city
        }
    
    def _search_availability(self, parsed: dict) -> List[Dict[str, Any]]:
        """Search OpenTable/Resy for availability."""
        opentable_key = os.getenv("OPENTABLE_API_KEY")
        resy_key = os.getenv("RESY_API_KEY")
        
        if not opentable_key and not resy_key:
            logger.warning("No restaurant API keys configured")
            return []  # Caller handles empty list as no results
        
        options = []
        
        # Try OpenTable first if available
        if opentable_key:
            opentable_results = self._search_opentable(parsed)
            options.extend(opentable_results)
        
        # Try Resy if available
        if resy_key:
            resy_results = self._search_resy(parsed)
            options.extend(resy_results)
        
        # Sort by recommendation score or time proximity
        options.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        # Return top 3 options
        return options[:3]
    
    def _search_opentable(self, parsed: dict) -> List[Dict[str, Any]]:
        """Search OpenTable API for availability."""
        try:
            # Mock implementation - in real scenario would call OpenTable API
            # Example API call:
            # headers = {"Authorization": f"Bearer {OPENTABLE_API_KEY}"}
            # params = {
            #     "city": parsed['city'],
            #     "date": parsed['date'],
            #     "time": parsed['time'],
            #     "party_size": parsed['party_size'],
            #     "cuisine": parsed['cuisine']
            # }
            # response = requests.get(f"{self.opentable_base_url}/availability", headers=headers, params=params)
            
            logger.info(f"Searching OpenTable for {parsed}")
            
            # Mock data for demonstration
            restaurant_names = [
                f"{parsed['cuisine'].title()} Bistro",
                f"The {parsed['cuisine'].title()} Kitchen",
                f"Modern {parsed['cuisine'].title()}"
            ]
            
            options = []
            for i, name in enumerate(restaurant_names):
                # Create slightly different times
                hour = int(parsed['time'].split(':')[0])
                time_options = [f"{hour}:00", f"{hour}:30", f"{hour+1}:00"]
                
                options.append({
                    'restaurant': name,
                    'date': parsed['date'],
                    'time': time_options[i % len(time_options)],
                    'party_size': parsed['party_size'],
                    'cuisine': parsed['cuisine'],
                    'provider': 'opentable',
                    'restaurant_id': f"ot_{i}",
                    'score': 0.9 - (i * 0.1),  # Mock score
                    'price_range': '$$',
                    'address': f"{i} Main St, {parsed['city']}",
                    'rating': 4.5 - (i * 0.2)
                })
            
            return options
            
        except Exception as e:
            logger.error(f"OpenTable search error: {e}")
            return []
    
    def _search_resy(self, parsed: dict) -> List[Dict[str, Any]]:
        """Search Resy API for availability."""
        try:
            # Mock implementation - in real scenario would call Resy API
            # Example API call:
            # headers = {
            #     "Authorization": f"Bearer {RESY_API_KEY}",
            #     "Content-Type": "application/json"
            # }
            # params = {
            #     "venue_id": "123",  # Would need venue search first
            #     "party_size": parsed['party_size'],
            #     "day": parsed['date'],
            #     "time": parsed['time']
            # }
            # response = requests.get(f"{self.resy_base_url}/3/venue/availability", headers=headers, params=params)
            
            logger.info(f"Searching Resy for {parsed}")
            
            # Mock data for demonstration
            restaurant_names = [
                f"Resy {parsed['cuisine'].title()} House",
                f"{parsed['cuisine'].title()} Reserve",
                f"Signature {parsed['cuisine'].title()}"
            ]
            
            options = []
            for i, name in enumerate(restaurant_names):
                # Create slightly different times
                hour = int(parsed['time'].split(':')[0])
                time_options = [f"{hour - 1}:30", f"{hour}:00", f"{hour + 1}:30"]
                
                options.append({
                    'restaurant': name,
                    'date': parsed['date'],
                    'time': time_options[i % len(time_options)],
                    'party_size': parsed['party_size'],
                    'cuisine': parsed['cuisine'],
                    'provider': 'resy',
                    'restaurant_id': f"resy_{i}",
                    'score': 0.8 - (i * 0.1),  # Mock score
                    'price_range': '$$$',
                    'address': f"{i} Park Ave, {parsed['city']}",
                    'rating': 4.3 - (i * 0.2)
                })
            
            return options
            
        except Exception as e:
            logger.error(f"Resy search error: {e}")
            return []
    
    def _confirm_reservation(self, option: dict, user_id: str) -> dict:
        """Confirm the reservation via API."""
        opentable_key = os.getenv("OPENTABLE_API_KEY")
        resy_key = os.getenv("RESY_API_KEY")
        
        if not opentable_key and not resy_key:
            return {"success": False, "error": "No restaurant integration configured. Connect OpenTable or Resy in Settings."}
        
        try:
            if option.get('provider') == 'opentable' and opentable_key:
                return self._confirm_opentable_reservation(option, user_id)
            elif option.get('provider') == 'resy' and resy_key:
                return self._confirm_resy_reservation(option, user_id)
            else:
                # Default fallback based on available API
                if opentable_key:
                    return self._confirm_opentable_reservation(option, user_id)
                elif resy_key:
                    return self._confirm_resy_reservation(option, user_id)
            
        except Exception as e:
            logger.error(f"Reservation confirmation error: {e}")
            return {"success": False, "error": f"Reservation failed: {str(e)}"}
    
    def _confirm_opentable_reservation(self, option: dict, user_id: str) -> dict:
        """Confirm reservation via OpenTable API."""
        try:
            # Mock implementation
            # headers = {"Authorization": f"Bearer {OPENTABLE_API_KEY}"}
            # payload = {
            #     "restaurant_id": option['restaurant_id'],
            #     "date": option['date'],
            #     "time": option['time'],
            #     "party_size": option['party_size'],
            #     "user_details": {
            #         "name": "User",  # Would come from user profile
            #         "email": "user@example.com",
            #         "phone": "+1234567890"
            #     }
            # }
            # response = requests.post(f"{self.opentable_base_url}/reservations", json=payload, headers=headers)
            
            logger.info(f"Confirming OpenTable reservation: {option['restaurant']} at {option['time']}")
            
            # Simulate API delay
            time.sleep(0.5)
            
            # Mock successful response
            confirmation_id = f"OT{int(time.time())}{option['restaurant_id']}"
            
            return {
                "success": True,
                "confirmation_id": confirmation_id,
                "provider": "opentable",
                "message": f"Reservation confirmed at {option['restaurant']} for {option['date']} at {option['time']} for {option['party_size']} people.",
                "details": {
                    "cancellation_policy": "Cancel up to 24 hours in advance",
                    "confirmation_email_sent": True
                }
            }
            
        except Exception as e:
            logger.error(f"OpenTable reservation error: {e}")
            return {"success": False, "error": f"OpenTable reservation failed: {str(e)}"}
    
    def _confirm_resy_reservation(self, option: dict, user_id: str) -> dict:
        """Confirm reservation via Resy API."""
        try:
            # Mock implementation
            # headers = {
            #     "Authorization": f"Bearer {RESY_API_KEY}",
            #     "Content-Type": "application/json"
            # }
            # payload = {
            #     "venue_id": option['restaurant_id'],
            #     "day": option['date'],
            #     "time": option['time'],
            #     "party_size": option['party_size'],
            #     "user": {
            #         "first_name": "User",
            #         "last_name": "Name",
            #         "email": "user@example.com",
            #         "phone": "+1234567890"
            #     }
            # }
            # response = requests.post(f"{self.resy_base_url}/3/reservation", json=payload, headers=headers)
            
            logger.info(f"Confirming Resy reservation: {option['restaurant']} at {option['time']}")
            
            # Simulate API delay
            time.sleep(0.5)
            
            # Mock successful response
            confirmation_id = f"RESY{int(time.time())}{option['restaurant_id']}"
            
            return {
                "success": True,
                "confirmation_id": confirmation_id,
                "provider": "resy",
                "message": f"Reservation confirmed at {option['restaurant']} for {option['date']} at {option['time']} for {option['party_size']} people.",
                "details": {
                    "cancellation_policy": "Cancel up to 2 hours in advance",
                    "confirmation_email_sent": True,
                    "resy_link": f"https://resy.com/reservations/{confirmation_id}"
                }
            }
            
        except Exception as e:
            logger.error(f"Resy reservation error: {e}")
            return {"success": False, "error": f"Resy reservation failed: {str(e)}"}
    
    def _create_calendar_event(self, option: dict, user_id: str):
        """Create calendar event for reservation."""
        # Would integrate with Google Calendar API
        logger.info(f"Would create calendar event for {option['restaurant']} at {option['time']} on {option['date']}")
        # In real implementation:
        # 1. Get user's calendar integration tokens
        # 2. Create event with reservation details
        # 3. Add confirmation number to description


restaurant_skill = RestaurantReservationSkill()