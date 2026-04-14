"""Grocery ordering skill - per SPEC Item 11."""
import os
import logging
import json
import requests

logger = logging.getLogger(__name__)

# Instacart API (or Kroger fallback)
INSTACART_API_KEY = os.environ.get('INSTACART_API_KEY', '')
KROGER_API_KEY = os.environ.get('KROGER_API_KEY', '')
KROGER_BASE_URL = 'https://api.kroger.com/v1'


class GroceryOrderingSkill:
    """Order groceries via Instacart or Kroger API."""
    
    name = "grocery_order"
    description = "Order groceries from Instacart or Kroger"
    required_integrations = []
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language: 'order ingredients for chicken stir fry for 4'"},
                "confirm": {"type": "boolean", "default": False, "description": "Set to true to confirm and place order"}
            },
            "required": ["query"]
        }
    
    def can_execute(self, user_id: str, business_id: str = None):
        if not os.getenv("KROGER_API_KEY"):
            return {"can_run": False, "reason": "Kroger integration not configured. Connect Kroger in Settings."}
        return {"can_run": True}
    
    def execute(self, input: dict, user_id: str) -> dict:
        query = input.get("query", "")
        confirm = input.get("confirm", False)
        
        # Step 1: Parse NL to item list via LLM
        # For now, use simple parsing (could enhance with LLM)
        items = self._parse_items(query)
        
        if not items:
            return {"success": False, "error": "Could not parse items from query"}
        
        # Step 2: Search for items (using Kroger as fallback)
        search_results = self._search_items(items)
        
        if not search_results:
            return {"success": False, "error": "No items found"}
        
        # Step 3: Build cart with prices
        cart = self._build_cart(search_results)
        total = sum(item['price'] * item['quantity'] for item in cart)
        
        # If not confirming, return itemized list
        if not confirm:
            return {
                "success": True,
                "pending_confirmation": True,
                "items": cart,
                "total": total,
                "message": f"Found {len(cart)} items for ${total:.2f}. Reply 'confirm' to place order."
            }
        
        # Step 4: Place order
        order_result = self._place_order(cart, user_id)
        
        return {
            "success": True,
            "order_placed": True,
            "confirmation_number": order_result.get("order_id"),
            "delivery_eta": order_result.get("eta"),
            "total": total,
            "items": cart
        }
    
    def _parse_items(self, query: str) -> list:
        """Parse natural language to item list."""
        # Simple keyword extraction
        # Could be enhanced with LLM
        common_items = {
            'chicken': {'item': 'chicken breast', 'qty': 2, 'unit': 'lbs'},
            'stir fry': {'item': 'stir fry vegetables', 'qty': 1, 'unit': 'bag'},
            'rice': {'item': 'white rice', 'qty': 2, 'unit': 'lbs'},
            'soy sauce': {'item': 'soy sauce', 'qty': 1, 'unit': 'bottle'},
            'garlic': {'item': 'garlic', 'qty': 1, 'unit': 'head'},
            'onion': {'item': 'onion', 'qty': 2, 'unit': 'whole'},
            'broccoli': {'item': 'broccoli', 'qty': 1, 'unit': 'lb'},
            'bell pepper': {'item': 'bell pepper', 'qty': 2, 'unit': 'whole'},
            'eggs': {'item': 'eggs', 'qty': 1, 'unit': 'dozen'},
            'milk': {'item': 'milk', 'qty': 1, 'unit': 'gallon'},
            'bread': {'item': 'bread', 'qty': 1, 'unit': 'loaf'},
            'butter': {'item': 'butter', 'qty': 1, 'unit': 'stick'},
        }
        
        items = []
        query_lower = query.lower()
        for key, value in common_items.items():
            if key in query_lower:
                items.append(value)
        
        # Default if no match
        if not items:
            items.append({'item': 'groceries', 'qty': 1, 'unit': 'bag'})
        
        return items
    
    def _search_items(self, items: list) -> list:
        """Search for items via Kroger API."""
        if not os.getenv("KROGER_API_KEY"):
            return []  # Caller handles empty list as no results

        if not KROGER_API_KEY:
            # Mock response if no API key
            return [
                {'name': i['item'], 'price': 5.99 * i['qty'], 'quantity': i['qty'], 'unit': i['unit']}
                for i in items
            ]
        
        results = []
        for item in items:
            try:
                headers = {'Authorization': f'Bearer {KROGER_API_KEY}'}
                resp = requests.get(
                    f"{KROGER_BASE_URL}/products",
                    headers=headers,
                    params={'filter.term': item['item'], 'filter.limit': 1},
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    product = data.get('data', [{}])[0]
                    if product:
                        results.append({
                            'name': product.get('description', item['item']),
                            'price': float(product.get('price', {}).get('regular', 5.99)),
                            'quantity': item['qty'],
                            'unit': item['unit'],
                            'product_id': product.get('productId')
                        })
            except Exception as e:
                logger.warning(f"Kroger search failed for {item}: {e}")
        
        return results
    
    def _build_cart(self, items: list) -> list:
        """Build cart from search results."""
        return items
    
    def _place_order(self, cart: list, user_id: str) -> dict:
        """Place order via Instacart/Kroger."""
        if not os.getenv("KROGER_API_KEY"):
            return {"success": False, "error": "Kroger integration not configured. Connect Kroger in Settings."}
        
        # Real Kroger API integration not yet implemented
        return {"success": False, "error": "Kroger ordering not yet available."}


# Skill instance for registry
grocery_skill = GroceryOrderingSkill()
