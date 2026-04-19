"""
OpenTable Adapter
=================
Restaurant reservation integration for OpenTable.

This module provides a wrapper for the OpenTable API with methods for
searching restaurants, checking availability, and making reservations.
"""

import logging
import requests
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class OpenTableAdapter:
    """
    OpenTable restaurant reservation integration.
    
    Usage:
        adapter = OpenTableAdapter(auth_token="your_api_token")
        
        # Search for restaurants
        restaurants = adapter.search(
            location="New York, NY",
            party_size=2,
            date="2023-12-25"
        )
        
        # Check availability
        availability = adapter.check_availability(
            restaurant_id=12345,
            party_size=2,
            date="2023-12-25",
            time="19:00"
        )
        
        # Make a reservation
        reservation = adapter.book(
            restaurant_id=12345,
            party_size=2,
            date="2023-12-25",
            time="19:00",
            customer_details={"name": "John Doe", "email": "john@example.com"}
        )
    """
    
    # Capabilities for operator layer
    capabilities = [
        "search_restaurants",
        "check_availability",
        "book_reservation",
        "cancel_reservation",
        "get_reservation_details",
    ]
    
    API_BASE = "https://api.opentable.com/v1"
    
    def __init__(self, auth_token: str = None):
        """
        Initialize the OpenTable adapter.
        
        Args:
            auth_token: OpenTable API authentication token.
                       If not provided, will attempt to get from credential store.
        """
        self.auth_token = auth_token
        self.session = requests.Session()
        
        if auth_token:
            self.session.headers.update({
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            })
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make a request to the OpenTable API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (without base URL)
            **kwargs: Additional arguments to pass to requests
            
        Returns:
            JSON response as dictionary
            
        Raises:
            requests.exceptions.RequestException: On API error
        """
        url = f"{self.API_BASE}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenTable API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            raise
    
    def search(self, 
               location: str,
               party_size: int = 2,
               date: str = None,
               time: str = None,
               cuisine: str = None,
               price_range: str = None,
               limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for restaurants on OpenTable.
        
        Args:
            location: City, state, or zip code (e.g., "New York, NY")
            party_size: Number of people for the reservation
            date: Reservation date in YYYY-MM-DD format (optional)
            time: Reservation time in HH:MM format (optional)
            cuisine: Type of cuisine (optional)
            price_range: Price range (e.g., "$", "$$", "$$$") (optional)
            limit: Maximum number of results to return
            
        Returns:
            List of restaurant dictionaries
        """
        params = {
            "location": location,
            "party_size": party_size,
            "limit": limit
        }
        
        if date:
            params["date"] = date
        if time:
            params["time"] = time
        if cuisine:
            params["cuisine"] = cuisine
        if price_range:
            params["price_range"] = price_range
        
        logger.info(f"Searching OpenTable for restaurants in {location} "
                   f"for {party_size} people")
        
        response = self._request("GET", "restaurants/search", params=params)
        
        # Extract restaurants from response
        restaurants = response.get("restaurants", [])
        logger.info(f"Found {len(restaurants)} restaurants")
        
        return restaurants
    
    def check_availability(self,
                          restaurant_id: int,
                          party_size: int,
                          date: str,
                          time: str = None) -> List[Dict[str, Any]]:
        """
        Check reservation availability for a specific restaurant.
        
        Args:
            restaurant_id: OpenTable restaurant ID
            party_size: Number of people for the reservation
            date: Reservation date in YYYY-MM-DD format
            time: Reservation time in HH:MM format (optional)
                   If not provided, returns all available times for the date
            
        Returns:
            List of available time slots
        """
        params = {
            "restaurant_id": restaurant_id,
            "party_size": party_size,
            "date": date
        }
        
        if time:
            params["time"] = time
        
        logger.info(f"Checking availability for restaurant {restaurant_id} "
                   f"on {date} for {party_size} people")
        
        response = self._request("GET", "availability", params=params)
        
        # Extract availability slots from response
        slots = response.get("availability", [])
        logger.info(f"Found {len(slots)} available time slots")
        
        return slots
    
    def book(self,
             restaurant_id: int,
             party_size: int,
             date: str,
             time: str,
             customer_details: Dict[str, str],
             special_requests: str = None) -> Dict[str, Any]:
        """
        Make a reservation at a restaurant.
        
        Args:
            restaurant_id: OpenTable restaurant ID
            party_size: Number of people for the reservation
            date: Reservation date in YYYY-MM-DD format
            time: Reservation time in HH:MM format
            customer_details: Dictionary with customer information
                             Required keys: "name", "email", "phone"
            special_requests: Special requests for the reservation (optional)
            
        Returns:
            Reservation confirmation details
        """
        # Validate required customer details
        required_fields = ["name", "email", "phone"]
        for field in required_fields:
            if field not in customer_details:
                raise ValueError(f"Missing required customer field: {field}")
        
        payload = {
            "restaurant_id": restaurant_id,
            "party_size": party_size,
            "date": date,
            "time": time,
            "customer": customer_details
        }
        
        if special_requests:
            payload["special_requests"] = special_requests
        
        logger.info(f"Making reservation at restaurant {restaurant_id} "
                   f"on {date} at {time} for {party_size} people")
        
        response = self._request("POST", "reservations", json=payload)
        
        reservation_id = response.get("reservation_id")
        logger.info(f"Reservation confirmed with ID: {reservation_id}")
        
        return response
    
    def cancel(self, reservation_id: str) -> bool:
        """
        Cancel an existing reservation.
        
        Args:
            reservation_id: OpenTable reservation ID
            
        Returns:
            True if cancellation was successful
        """
        logger.info(f"Cancelling reservation {reservation_id}")
        
        try:
            self._request("DELETE", f"reservations/{reservation_id}")
            logger.info(f"Reservation {reservation_id} cancelled successfully")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to cancel reservation {reservation_id}: {e}")
            return False
    
    def get_reservation_details(self, reservation_id: str) -> Dict[str, Any]:
        """
        Get details of a specific reservation.
        
        Args:
            reservation_id: OpenTable reservation ID
            
        Returns:
            Reservation details
        """
        logger.info(f"Getting details for reservation {reservation_id}")
        
        return self._request("GET", f"reservations/{reservation_id}")