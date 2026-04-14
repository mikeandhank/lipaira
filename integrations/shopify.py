"""
Shopify Adapter
===============
Shopify Admin API integration for e-commerce management.

Shopify uses access tokens (not OAuth) - client needs to generate from their store.
"""

import os
import json
import logging
import requests
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

# Shopify API base
SHOPIFY_API_VERSION = "2024-01"


class ShopifyAdapter:
    """Adapter for Shopify Admin API."""
    
    # Capabilities for operator layer
    capabilities = [
        "update_prices",
        "update_inventory",
        "fulfill_orders",
        "sync_products",
        "check_health",
        "query",
    ]

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.credentials = None
        self._load_credentials()

    def _load_credentials(self):
        """Load credentials from credential store."""
        from .credential_store import IntegrationCredentialStore
        store = IntegrationCredentialStore(self.user_id)
        self.credentials = store.get("shopify")

    def is_connected(self) -> bool:
        """Check if connected to Shopify."""
        return self.credentials is not None and bool(
            self.credentials.get("access_token") and self.credentials.get("shop_domain")
        )

    def _get_headers(self) -> Dict[str, str]:
        """Get API headers with access token."""
        return {
            "X-Shopify-Access-Token": self.credentials["access_token"],
            "Content-Type": "application/json",
        }

    def _api_url(self, path: str) -> str:
        """Build full API URL."""
        shop_domain = self.credentials["shop_domain"]
        # Ensure shop_domain doesn't have protocol
        shop_domain = shop_domain.replace("https://", "").replace("http://", "").rstrip("/")
        base_url = f"https://{shop_domain}/admin/api/{SHOPIFY_API_VERSION}"
        return urljoin(base_url, path.lstrip("/"))

    def verify_connection(self) -> Dict[str, Any]:
        """
        Verify Shopify connection by fetching shop info.
        
        Returns:
            {"success": bool, "shop": dict, "message": str, "products_count": int}
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected to Shopify"}

        try:
            response = requests.get(
                self._api_url("/shop.json"),
                headers=self._get_headers(),
                timeout=30
            )

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"API error: {response.status_code}"
                }

            shop = response.json().get("shop", {})
            
            # Get product count
            products_response = requests.get(
                self._api_url("/products/count.json"),
                headers=self._get_headers(),
                timeout=30
            )
            products_count = products_response.json().get("count", 0) if products_response.status_code == 200 else 0

            return {
                "success": True,
                "shop": {
                    "name": shop.get("name"),
                    "domain": shop.get("domain"),
                    "email": shop.get("email"),
                    "plan": shop.get("plan_display_name"),
                },
                "message": f"Connected to {shop.get('name')}",
                "products_count": products_count,
            }

        except requests.RequestException as e:
            logger.error(f"Shopify connection error: {e}")
            return {"success": False, "error": str(e)}

    def list_products(self, limit: int = 50, status: str = "active") -> List[Dict]:
        """
        List products from Shopify store.
        
        Args:
            limit: Max products to fetch (max 250)
            status: Filter by status (any, active, archived, draft)
            
        Returns:
            List of product dictionaries
        """
        if not self.is_connected():
            return []

        try:
            response = requests.get(
                self._api_url(f"/products.json?limit={min(limit, 250)}&status={status}"),
                headers=self._get_headers(),
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Shopify products error: {response.status_code}")
                return []

            return response.json().get("products", [])

        except requests.RequestException as e:
            logger.error(f"Shopify API error: {e}")
            return []

    def get_product(self, product_id: int) -> Optional[Dict]:
        """Get single product by ID."""
        if not self.is_connected():
            return None

        try:
            response = requests.get(
                self._api_url(f"/products/{product_id}.json"),
                headers=self._get_headers(),
                timeout=30
            )

            if response.status_code == 200:
                return response.json().get("product")
            return None

        except requests.RequestException as e:
            logger.error(f"Shopify API error: {e}")
            return None

    def update_product_price(self, product_id: int, price: float) -> Dict[str, Any]:
        """
        Update product price (variants).
        
        Args:
            product_id: Shopify product ID
            price: New price in USD
            
        Returns:
            {"success": bool, "product": dict}
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        product = self.get_product(product_id)
        if not product:
            return {"success": False, "error": "Product not found"}

        # Update all variants with new price
        variants = product.get("variants", [])
        variant_ids = [v["id"] for v in variants]

        if not variant_ids:
            return {"success": False, "error": "No variants found"}

        try:
            # Shopify requires updating via inventory item or variant
            # Simplest: update each variant's price
            for variant_id in variant_ids:
                response = requests.put(
                    self._api_url(f"/variants/{variant_id}.json"),
                    headers=self._get_headers(),
                    json={
                        "variant": {
                            "id": variant_id,
                            "price": f"{price:.2f}"
                        }
                    },
                    timeout=30
                )

                if response.status_code != 200:
                    return {"success": False, "error": f"Failed to update variant {variant_id}"}

            return {
                "success": True,
                "message": f"Updated price to ${price:.2f} for {len(variant_ids)} variant(s)"
            }

        except requests.RequestException as e:
            logger.error(f"Shopify price update error: {e}")
            return {"success": False, "error": str(e)}

    def update_inventory(self, inventory_item_id: int, quantity: int, location_id: int = None) -> Dict[str, Any]:
        """
        Update inventory level for a product variant.
        
        Args:
            inventory_item_id: Shopify inventory_item_id (from variant)
            quantity: New quantity (-1 for unlimited)
            location_id: Required for inventory updates
            
        Returns:
            {"success": bool}
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        if not location_id:
            # Get default location
            location_id = self._get_default_location()
            if not location_id:
                return {"success": False, "error": "No location found. Provide location_id."}

        try:
            # Set inventory level
            response = requests.post(
                self._api_url("/inventory_levels/set.json"),
                headers=self._get_headers(),
                json={
                    "location_id": location_id,
                    "inventory_item_id": inventory_item_id,
                    "available": quantity if quantity >= 0 else 0,
                },
                timeout=30
            )

            if response.status_code != 200:
                return {"success": False, "error": f"API error: {response.status_code}"}

            return {
                "success": True,
                "message": f"Updated inventory to {quantity}"
            }

        except requests.RequestException as e:
            logger.error(f"Shopify inventory update error: {e}")
            return {"success": False, "error": str(e)}

    def _get_default_location(self) -> Optional[int]:
        """Get the first inventory location ID."""
        try:
            response = requests.get(
                self._api_url("/locations.json"),
                headers=self._get_headers(),
                timeout=30
            )

            if response.status_code == 200:
                locations = response.json().get("locations", [])
                if locations:
                    return locations[0]["id"]
        except:
            pass
        return None

    def list_orders(self, status: str = "any", limit: int = 50) -> List[Dict]:
        """
        List orders from Shopify.
        
        Args:
            status: Filter (any, open, closed, cancelled)
            limit: Max orders (max 250)
            
        Returns:
            List of order dictionaries
        """
        if not self.is_connected():
            return []

        try:
            response = requests.get(
                self._api_url(f"/orders.json?status={status}&limit={min(limit, 250)}"),
                headers=self._get_headers(),
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Shopify orders error: {response.status_code}")
                return []

            return response.json().get("orders", [])

        except requests.RequestException as e:
            logger.error(f"Shopify API error: {e}")
            return []

    def get_order(self, order_id: int) -> Optional[Dict]:
        """Get single order by ID."""
        if not self.is_connected():
            return None

        try:
            response = requests.get(
                self._api_url(f"/orders/{order_id}.json"),
                headers=self._get_headers(),
                timeout=30
            )

            if response.status_code == 200:
                return response.json().get("order")
            return None

        except requests.RequestException as e:
            logger.error(f"Shopify API error: {e}")
            return None

    def fulfill_order(self, order_id: int, tracking_number: str = None, 
                      tracking_company: str = None, notify_customer: bool = True) -> Dict[str, Any]:
        """
        Fulfill an order (or part of an order).
        
        Args:
            order_id: Shopify order ID
            tracking_number: Optional tracking number
            tracking_company: Carrier (ups, fedex, usps, dhl, etc.)
            notify_customer: Send notification to customer
            
        Returns:
            {"success": bool, "fulfillment": dict}
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        order = self.get_order(order_id)
        if not order:
            return {"success": False, "error": "Order not found"}

        # Check if already fulfilled
        if order.get("fulfillment_status") == "fulfilled":
            return {"success": False, "error": "Order already fulfilled"}

        # Get line items that need fulfillment
        line_items = order.get("line_items", [])
        
        # Build fulfillment payload
        fulfillment = {
            "location_id": self._get_default_location(),
            "notify": notify_customer,
        }

        if tracking_number:
            fulfillment["tracking_numbers"] = [tracking_number]
        if tracking_company:
            fulfillment["tracking_company"] = tracking_company

        try:
            response = requests.post(
                self._api_url(f"/orders/{order_id}/fulfillments.json"),
                headers=self._get_headers(),
                json={"fulfillment": fulfillment},
                timeout=30
            )

            if response.status_code != 201 and response.status_code != 200:
                return {"success": False, "error": f"API error: {response.status_code}"}

            return {
                "success": True,
                "message": "Order fulfilled successfully",
                "fulfillment": response.json().get("fulfillment", {})
            }

        except requests.RequestException as e:
            logger.error(f"Shopify fulfillment error: {e}")
            return {"success": False, "error": str(e)}

    def create_fulfillment(self, order_id: int, line_items: List[Dict],
                          tracking_number: str = None, tracking_company: str = None) -> Dict[str, Any]:
        """
        Create partial fulfillment for specific line items.
        
        Args:
            order_id: Shopify order ID
            line_items: [{"id": line_item_id, "quantity": 2}]
            tracking_number: Optional tracking
            tracking_company: Carrier
            
        Returns:
            {"success": bool}
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        fulfillment = {
            "location_id": self._get_default_location(),
            "line_items": line_items,
        }

        if tracking_number:
            fulfillment["tracking_numbers"] = [tracking_number]
        if tracking_company:
            fulfillment["tracking_company"] = tracking_company

        try:
            response = requests.post(
                self._api_url(f"/orders/{order_id}/fulfillments.json"),
                headers=self._get_headers(),
                json={"fulfillment": fulfillment},
                timeout=30
            )

            if response.status_code not in (200, 201):
                return {"success": False, "error": f"API error: {response.status_code}"}

            return {"success": True, "message": "Partial fulfillment created"}

        except requests.RequestException as e:
            logger.error(f"Shopify fulfillment error: {e}")
            return {"success": False, "error": str(e)}

    def update_inventory_bulk(self, updates: List[Dict]) -> Dict[str, Any]:
        """
        Bulk update inventory levels.
        
        Args:
            updates: [{"inventory_item_id": int, "quantity": int, "location_id": int}]
            
        Returns:
            {"success": bool, "updated": int, "failed": int}
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        updated = 0
        failed = 0

        for update in updates:
            result = self.update_inventory(
                update["inventory_item_id"],
                update["quantity"],
                update.get("location_id")
            )
            if result["success"]:
                updated += 1
            else:
                failed += 1

        return {
            "success": failed == 0,
            "updated": updated,
            "failed": failed
        }

    def sync_products_to_database(self) -> Dict[str, Any]:
        """
        Sync all products to local database table.
        
        Creates/updates `shopify_products` table.
        """
        if not self.is_connected():
            return {"success": False, "error": "Not connected"}

        import psycopg2
        from psycopg2.extras import execute_values
        import os
        from urllib.parse import urlparse

        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            return {"success": False, "error": "DATABASE_URL not set"}

        result = urlparse(db_url)
        
        try:
            conn = psycopg2.connect(
                host=result.hostname,
                port=result.port or 5432,
                database=result.path.lstrip("/"),
                user=result.username,
                password=result.password
            )
        except Exception as e:
            return {"success": False, "error": f"DB connection failed: {e}"}

        try:
            # Create table if not exists
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS shopify_products (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        shopify_product_id BIGINT UNIQUE NOT NULL,
                        title TEXT,
                        handle TEXT,
                        vendor TEXT,
                        product_type TEXT,
                        status VARCHAR(50),
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP,
                        synced_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(user_id, shopify_product_id)
                    )
                """)
                
                # Create variant table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS shopify_product_variants (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        shopify_variant_id BIGINT UNIQUE NOT NULL,
                        shopify_product_id BIGINT NOT NULL,
                        title VARCHAR(500),
                        price DECIMAL(10,2),
                        sku VARCHAR(255),
                        inventory_item_id BIGINT,
                        inventory_quantity INTEGER,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP,
                        synced_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(user_id, shopify_variant_id)
                    )
                """)
                conn.commit()

            # Fetch products
            products = self.list_products(limit=250)
            
            if not products:
                return {"success": True, "message": "No products to sync", "count": 0}

            # Insert products
            product_rows = []
            variant_rows = []

            for p in products:
                product_rows.append((
                    self.user_id,
                    p["id"],
                    p.get("title"),
                    p.get("handle"),
                    p.get("vendor"),
                    p.get("product_type"),
                    p.get("status"),
                    p.get("created_at"),
                    p.get("updated_at"),
                ))

                for v in p.get("variants", []):
                    variant_rows.append((
                        self.user_id,
                        v["id"],
                        p["id"],
                        v.get("title"),
                        v.get("price"),
                        v.get("sku"),
                        v.get("inventory_item_id"),
                        v.get("inventory_quantity"),
                        v.get("created_at"),
                        v.get("updated_at"),
                    ))

            with conn.cursor() as cur:
                # Upsert products
                execute_values("""
                    INSERT INTO shopify_products 
                    (user_id, shopify_product_id, title, handle, vendor, product_type, status, created_at, updated_at)
                    VALUES %s
                    ON CONFLICT (user_id, shopify_product_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        handle = EXCLUDED.handle,
                        vendor = EXCLUDED.vendor,
                        product_type = EXCLUDED.product_type,
                        status = EXCLUDED.status,
                        updated_at = EXCLUDED.updated_at,
                        synced_at = NOW()
                """, product_rows)

                # Upsert variants
                execute_values("""
                    INSERT INTO shopify_product_variants
                    (user_id, shopify_variant_id, shopify_product_id, title, price, sku, 
                     inventory_item_id, inventory_quantity, created_at, updated_at)
                    VALUES %s
                    ON CONFLICT (user_id, shopify_variant_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        price = EXCLUDED.price,
                        sku = EXCLUDED.sku,
                        inventory_quantity = EXCLUDED.inventory_quantity,
                        updated_at = EXCLUDED.updated_at,
                        synced_at = NOW()
                """, variant_rows)

                conn.commit()

            return {
                "success": True,
                "message": f"Synced {len(products)} products and {len(variant_rows)} variants",
                "products": len(products),
                "variants": len(variant_rows)
            }

        except Exception as e:
            logger.error(f"Shopify sync error: {e}")
            return {"success": False, "error": str(e)}
        finally:
            conn.close()