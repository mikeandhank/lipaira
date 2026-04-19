"""
Instacart API Wrapper
=====================
Basic wrapper for Instacart API with search, add to cart, and checkout functionality.
"""

import logging
from typing import Dict, List, Optional, Any
import requests

logger = logging.getLogger(__name__)


class InstacartAdapter:
    """
    Instacart API wrapper for grocery shopping operations.
    
    Usage:
        api = InstacartAdapter(auth_token="your_token")
        results = api.search("organic milk")
        cart_item = api.add_to_cart(product_id="12345", quantity=2)
        checkout = api.checkout(cart_id="cart_123", payment_method="credit_card")
    """
    
    # Base API URL - this might need to be updated based on actual Instacart API
    BASE_URL = "https://api.instacart.com"
    API_VERSION = "v1"
    
    def __init__(self, auth_token: str):
        """
        Initialize Instacart API wrapper.
        
        Args:
            auth_token: Authentication token for Instacart API
        """
        self.auth_token = auth_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make HTTP request to Instacart API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (without base URL)
            **kwargs: Additional arguments for requests
            
        Returns:
            JSON response as dictionary
            
        Raises:
            requests.exceptions.HTTPError: If request fails
        """
        url = f"{self.BASE_URL}/{self.API_VERSION}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Instacart API request failed: {e}")
            raise
    
    def search(self, query: str, limit: int = 20, **kwargs) -> List[Dict[str, Any]]:
        """
        Search for products on Instacart.
        
        Args:
            query: Search query (e.g., "organic milk", "bananas")
            limit: Maximum number of results to return
            **kwargs: Additional search parameters
            
        Returns:
            List of product dictionaries
        """
        params = {
            "query": query,
            "limit": limit,
            **kwargs
        }
        
        response = self._make_request("GET", "search", params=params)
        return response.get("products", [])
    
    def add_to_cart(self, product_id: str, quantity: int = 1, 
                   cart_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Add a product to the shopping cart.
        
        Args:
            product_id: ID of the product to add
            quantity: Quantity to add
            cart_id: Optional cart ID (creates new cart if not provided)
            **kwargs: Additional cart item parameters
            
        Returns:
            Cart item information
        """
        data = {
            "product_id": product_id,
            "quantity": quantity,
            **kwargs
        }
        
        if cart_id:
            endpoint = f"carts/{cart_id}/items"
        else:
            endpoint = "carts/items"
            
        response = self._make_request("POST", endpoint, json=data)
        return response
    
    def checkout(self, cart_id: str, payment_method: str,
                shipping_address: Optional[Dict] = None,
                **kwargs) -> Dict[str, Any]:
        """
        Checkout with the current cart.
        
        Args:
            cart_id: ID of the cart to checkout
            payment_method: Payment method identifier
            shipping_address: Optional shipping address dictionary
            **kwargs: Additional checkout parameters
            
        Returns:
            Order confirmation information
        """
        data = {
            "cart_id": cart_id,
            "payment_method": payment_method,
            **kwargs
        }
        
        if shipping_address:
            data["shipping_address"] = shipping_address
            
        response = self._make_request("POST", f"carts/{cart_id}/checkout", json=data)
        return response
    
    def get_cart(self, cart_id: str) -> Dict[str, Any]:
        """
        Get cart details.
        
        Args:
            cart_id: ID of the cart
            
        Returns:
            Cart information
        """
        response = self._make_request("GET", f"carts/{cart_id}")
        return response
    
    def clear_cart(self, cart_id: str) -> Dict[str, Any]:
        """
        Clear all items from cart.
        
        Args:
            cart_id: ID of the cart to clear
            
        Returns:
            Confirmation response
        """
        response = self._make_request("DELETE", f"carts/{cart_id}/items")
        return response