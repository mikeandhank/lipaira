"""
Squarespace Adapter
====================
Website and Commerce integration for Squarespace.
"""

import os
import json
import logging
import requests
from typing import Dict, List, Optional

from .credential_store import IntegrationCredentialStore, get_db_connection
from .network_handler import NetworkHandler, IdempotencyManager, get_rate_limiter

logger = logging.getLogger(__name__)


class SquarespaceAdapter:
    """
    Squarespace Website and Commerce integration.
    
    Usage:
        adapter = SquarespaceAdapter(user_id)
        
        # Check if connected
        if not adapter.is_connected():
            return "Connect Squarespace first"
        
        # List websites
        websites = adapter.list_websites()
        
        # Get products
        products = adapter.get_products(website_id)
        
        # Update product price
        adapter.update_product_price(website_id, product_id, 2999)  # $29.99
    """

    # Capabilities for operator layer
    capabilities = [
        "update_prices",
        "update_inventory",
        "fulfill_orders",
        "sync_products",
        "check_health",
        "query",
    ]

    API_BASE = "https://api.squarespace.com/1.1"
    COMMERCE_API = "https://api.squarespace.com/1.1/commerce"

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.credential_store = IntegrationCredentialStore(user_id)
        self.network = get_network_handler()
        self.idempotency = IdempotencyManager(user_id)
        self._credentials = None

    def _get_credentials(self) -> Optional[Dict]:
        """Get and cache credentials."""
        if self._credentials is None:
            self._credentials = self.credential_store.get("squarespace")
        return self._credentials

    def is_connected(self) -> bool:
        """Check if Squarespace is connected."""
        creds = self._get_credentials()
        return creds is not None and bool(creds.get("access_token"))

    def _get_headers(self) -> Dict:
        """Get authorization headers."""
        creds = self._get_credentials()
        if not creds:
            raise ValueError("Squarespace not connected")
        
        return {
            "Authorization": f"Bearer {creds['access_token']}",
            "Content-Type": "application/json",
            "User-Agent": "Lipaira/1.0"
        }

    def _get_website_id(self) -> Optional[str]:
        """Get the website ID from stored credentials."""
        creds = self._get_credentials()
        return creds.get("site_id")

    # =========================================================================
    # WEBSITE OPERATIONS
    # =========================================================================

    def list_websites(self) -> List[Dict]:
        """List all Squarespace websites accessible."""
        
        def request():
            return requests.get(
                f"{self.API_BASE}/accounts/me/websites",
                headers=self._get_headers()
            )
        
        result = self.network.call("squarespace", 600, request)
        
        if not result["success"]:
            return []
        
        websites = result.get("data", {}).get("websites", [])
        return [
            {
                "id": w.get("id"),
                "name": w.get("name"),
                "domain": w.get("primaryDomain"),
                "template": w.get("templateName"),
                "created": w.get("createdOn"),
            }
            for w in websites
        ]

    def get_website_info(self, website_id: str) -> Dict:
        """Get detailed website information."""
        
        def request():
            return requests.get(
                f"{self.API_BASE}/websites/{website_id}",
                headers=self._get_headers()
            )
        
        result = self.network.call("squarespace", 600, request)
        
        if not result["success"]:
            return {}
        
        return result.get("data", {})

    # =========================================================================
    # PRODUCT OPERATIONS
    # =========================================================================

    def get_products(self, website_id: str, 
                     limit: int = 100) -> List[Dict]:
        """
        Get all products from a Squarespace website.
        
        Args:
            website_id: The Squarespace website ID
            limit: Max products to return (default 100)
            
        Returns:
            List of products with id, name, price, etc.
        """
        offset = 0
        all_products = []
        
        while offset < 1000:  # Max pagination
            def request():
                return requests.get(
                    f"{self.COMMERCE_API}/websites/{website_id}/products",
                    headers=self._get_headers(),
                    params={
                        "limit": min(limit, 100),
                        "offset": offset
                    }
                )
            
            result = self.network.call("squarespace", 600, request)
            
            if not result["success"]:
                break
            
            products = result.get("data", {}).get("products", [])
            if not products:
                break
            
            all_products.extend(products)
            
            if len(products) < limit:
                break
            
            offset += limit
        
        return all_products

    def get_product(self, website_id: str, product_id: str) -> Optional[Dict]:
        """Get a single product."""
        
        def request():
            return requests.get(
                f"{self.COMMERCE_API}/websites/{website_id}/products/{product_id}",
                headers=self._get_headers()
            )
        
        result = self.network.call("squarespace", 600, request)
        
        if result["success"]:
            return result.get("data", {})
        return None

    def update_product_price(self, website_id: str, product_id: str,
                            price_cents: int) -> Dict:
        """
        Update product price.
        
        Args:
            website_id: Squarespace website ID
            product_id: Product ID to update
            price_cents: New price in cents (e.g., 2999 for $29.99)
            
        Returns:
            {"success": bool, "message": str}
        """
        # Check idempotency
        identifier = f"{website_id}:{product_id}:{price_cents}"
        if not self.idempotency.check("squarespace", "update_price", identifier):
            return {
                "success": False,
                "error": "Just updated this price. Give me a moment.",
                "recoverable": True
            }

        def request():
            return requests.patch(
                f"{self.COMMERCE_API}/websites/{website_id}/products/{product_id}",
                headers=self._get_headers(),
                json={
                    "price": {
                        "value": price_cents / 100.0,  # Convert to dollars
                        "currency": "USD"  # Default to USD
                    }
                }
            )
        
        result = self.network.call("squarespace", 600, request)
        
        if result["success"]:
            self.idempotency.log_action(
                "squarespace", "update_product_price", "success",
                {"website_id": website_id, "product_id": product_id, "price": price_cents}
            )
            
            return {
                "success": True,
                "action": "updated",
                "message": f"Updated price to ${price_cents / 100:.2f}"
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to update price"),
            "recoverable": True
        }

    def update_product_inventory(self, website_id: str, product_id: str,
                                 quantity: int) -> Dict:
        """
        Update product inventory (stock) level.
        
        Args:
            website_id: Squarespace website ID
            product_id: Product ID to update
            quantity: New stock quantity (-1 for unlimited)
        """
        def request():
            return requests.patch(
                f"{self.COMMERCE_API}/websites/{website_id}/products/{product_id}",
                headers=self._get_headers(),
                json={
                    "inventory": {
                        "quantity": quantity,
                        "unlimited": quantity < 0
                    }
                }
            )
        
        result = self.network.call("squarespace", 600, request)
        
        if result["success"]:
            return {
                "success": True,
                "action": "updated",
                "message": f"Updated inventory to {quantity if quantity >= 0 else 'unlimited'}"
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to update inventory"),
            "recoverable": True
        }

    # =========================================================================
    # ORDER OPERATIONS
    # =========================================================================

    def get_orders(self, website_id: str, 
                   status: str = None) -> List[Dict]:
        """
        Get orders from a Squarespace website.
        
        Args:
            website_id: Squarespace website ID
            status: Optional filter (FULFILLED, UNFULFILLED, CANCELLED)
        """
        params = {}
        if status:
            params["status"] = status.upper()
        
        def request():
            return requests.get(
                f"{self.COMMERCE_API}/websites/{website_id}/orders",
                headers=self._get_headers(),
                params=params
            )
        
        result = self.network.call("squarespace", 600, request)
        
        if result["success"]:
            return result.get("data", {}).get("orders", [])
        return []

    def get_order(self, website_id: str, order_id: str) -> Optional[Dict]:
        """Get a single order."""
        
        def request():
            return requests.get(
                f"{self.COMMERCE_API}/websites/{website_id}/orders/{order_id}",
                headers=self._get_headers()
            )
        
        result = self.network.call("squarespace", 600, request)
        
        if result["success"]:
            return result.get("data", {})
        return None

    def fulfill_order(self, website_id: str, order_id: str,
                      tracking_number: str = None,
                      carrier: str = None) -> Dict:
        """
        Mark order as fulfilled.
        
        Args:
            website_id: Squarespace website ID
            order_id: Order ID to fulfill
            tracking_number: Optional tracking number
            carrier: Optional carrier (UPS, FEDEX, USPS, etc.)
        """
        def request():
            payload = {"fulfillment": {"status": "FULFILLED"}}
            if tracking_number:
                payload["fulfillment"]["trackingNumber"] = tracking_number
            if carrier:
                payload["fulfillment"]["carrier"] = carrier
                
            return requests.patch(
                f"{self.COMMERCE_API}/websites/{website_id}/orders/{order_id}",
                headers=self._get_headers(),
                json=payload
            )
        
        result = self.network.call("squarespace", 600, request)
        
        if result["success"]:
            return {
                "success": True,
                "action": "fulfilled",
                "message": "Order marked as fulfilled"
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to fulfill order"),
            "recoverable": True
        }

    # =========================================================================
    # INVENTORY SYNC
    # =========================================================================

    def sync_products_to_database(self, website_id: str) -> Dict:
        """
        Sync all products to local database.
        
        Returns:
            {"success": bool, "synced": count, "message": str}
        """
        products = self.get_products(website_id)
        
        if not products:
            return {
                "success": False,
                "error": "Failed to fetch products"
            }
        
        synced = 0
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for p in products:
                    # Parse price from Squarespace format
                    price = p.get("price", {})
                    price_cents = int(price.get("value", 0) * 100) if price else 0
                    
                    cur.execute("""
                        INSERT INTO integration_products
                        (user_id, provider, external_id, name, price_cents, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (user_id, provider, external_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            price_cents = EXCLUDED.price_cents,
                            metadata = EXCLUDED.metadata,
                            updated_at = NOW()
                    """, (
                        self.user_id,
                        "squarespace",
                        p.get("id"),
                        p.get("name"),
                        price_cents,
                        json.dumps(p)
                    ))
                    synced += 1
                
                conn.commit()
        
        self.idempotency.log_action(
            "squarespace", "sync_products", "success",
            {"website_id": website_id, "synced": synced}
        )
        
        return {
            "success": True,
            "synced": synced,
            "message": f"Synced {synced} products from Squarespace"
        }

    # =========================================================================
    # UTILITY
    # =========================================================================

    def verify_connection(self) -> Dict:
        """Verify the connection works."""
        if not self.is_connected():
            return {
                "success": False,
                "error": "Not connected to Squarespace"
            }
        
        try:
            websites = self.list_websites()
            return {
                "success": True,
                "websites": len(websites),
                "message": f"Connected! Found {len(websites)} website(s)."
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Convenience function
def get_adapter(user_id: str) -> SquarespaceAdapter:
    """Get Squarespace adapter instance."""
    return SquarespaceAdapter(user_id)