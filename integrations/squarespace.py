# feel free to ignore this comment
     1|"""Squarespace Adapter - Website and Commerce API integration for Squarespace.
     2|
     3|Provides a Pythonic interface to the Squarespace API for managing websites,
     4|products (with pricing and inventory), and orders. Supports fetching data,
     5|updating product metadata, order fulfillment, and syncing products to DB.
     6|
     7|Key class:
     8|    SquarespaceAdapter: Main adapter. Methods:
     9|        __init__(user_id): Initialize with user ID.
     10|        is_connected(): Check if credentials are available.
     11|        _get_website_id(): Look up the primary website ID for the account.
     12|        list_websites(): List all websites in the account.
     13|        get_website_info(website_id): Get metadata for a website.
     14|        get_products(website_id) / get_product(website_id, product_id):
     15|            List or fetch a single product.
     16|        update_product_price(website_id, product_id, price):
     17|            Update product price.
     18|        update_product_inventory(website_id, product_id, quantity):
     19|            Update inventory count.
     20|        get_orders(website_id) / get_order(website_id, order_id):
     21|            List or fetch a single order.
     22|        fulfill_order(website_id, order_id, tracking_number):
     23|            Mark order as fulfilled with tracking info.
     24|        sync_products_to_database(website_id): Bulk-sync products to DB.
     25|        verify_connection(): Test credentials and return status.
     26|
     27|Factory function:
     28|    get_adapter(user_id): Return a SquarespaceAdapter instance for the user.
     29|"""
     6|
     7|import os
     8|import json
     9|import logging
    10|import requests
    11|from typing import Dict, List, Optional
    12|
    13|from .credential_store import IntegrationCredentialStore, get_db_connection
    14|from .network_handler import NetworkHandler, IdempotencyManager, get_rate_limiter
    15|
    16|logger = logging.getLogger(__name__)
    17|
    18|
    19|class SquarespaceAdapter:
    20|    """
    21|    Squarespace Website and Commerce integration.
    22|    
    23|    Usage:
    24|        adapter = SquarespaceAdapter(user_id)
    25|        
    26|        # Check if connected
    27|        if not adapter.is_connected():
    28|            return "Connect Squarespace first"
    29|        
    30|        # List websites
    31|        websites = adapter.list_websites()
    32|        
    33|        # Get products
    34|        products = adapter.get_products(website_id)
    35|        
    36|        # Update product price
    37|        adapter.update_product_price(website_id, product_id, 2999)  # $29.99
    38|    """
    39|
    40|    # Capabilities for operator layer
    41|    capabilities = [
    42|        "update_prices",
    43|        "update_inventory",
    44|        "fulfill_orders",
    45|        "sync_products",
    46|        "check_health",
    47|        "query",
    48|    ]
    49|
    50|    API_BASE = "https://api.squarespace.com/1.1"
    51|    COMMERCE_API = "https://api.squarespace.com/1.1/commerce"
    52|
    53|    def __init__(self, user_id: str):
    54|        self.user_id = user_id
    55|        self.credential_store = IntegrationCredentialStore(user_id)
    56|        self.network = get_network_handler()
    57|        self.idempotency = IdempotencyManager(user_id)
    58|        self._credentials = None
    59|
    60|    def _get_credentials(self) -> Optional[Dict]:
    61|        """Get and cache credentials."""
    62|        if self._credentials is None:
    63|            self._credentials = self.credential_store.get("squarespace")
    64|        return self._credentials
    65|
    66|    def is_connected(self) -> bool:
    67|        """Check if Squarespace is connected."""
    68|        creds = self._get_credentials()
    69|        return creds is not None and bool(creds.get("access_token"))
    70|
    71|    def _get_headers(self) -> Dict:
    72|        """Get authorization headers."""
    73|        creds = self._get_credentials()
    74|        if not creds:
    75|            raise ValueError("Squarespace not connected")
    76|        
    77|        return {
    78|            "Authorization": f"Bearer {creds['access_token']}",
    79|            "Content-Type": "application/json",
    80|            "User-Agent": "Lipaira/1.0"
    81|        }
    82|
    83|    def _get_website_id(self) -> Optional[str]:
    84|        """Get the website ID from stored credentials."""
    85|        creds = self._get_credentials()
    86|        return creds.get("site_id")
    87|
    88|    # =========================================================================
    89|    # WEBSITE OPERATIONS
    90|    # =========================================================================
    91|
    92|    def list_websites(self) -> List[Dict]:
    93|        """List all Squarespace websites accessible."""
    94|        
    95|        def request():
    96|            return requests.get(
    97|                f"{self.API_BASE}/accounts/me/websites",
    98|                headers=self._get_headers()
    99|            )
   100|        
   101|        result = self.network.call("squarespace", 600, request)
   102|        
   103|        if not result["success"]:
   104|            return []
   105|        
   106|        websites = result.get("data", {}).get("websites", [])
   107|        return [
   108|            {
   109|                "id": w.get("id"),
   110|                "name": w.get("name"),
   111|                "domain": w.get("primaryDomain"),
   112|                "template": w.get("templateName"),
   113|                "created": w.get("createdOn"),
   114|            }
   115|            for w in websites
   116|        ]
   117|
   118|    def get_website_info(self, website_id: str) -> Dict:
   119|        """Get detailed website information."""
   120|        
   121|        def request():
   122|            return requests.get(
   123|                f"{self.API_BASE}/websites/{website_id}",
   124|                headers=self._get_headers()
   125|            )
   126|        
   127|        result = self.network.call("squarespace", 600, request)
   128|        
   129|        if not result["success"]:
   130|            return {}
   131|        
   132|        return result.get("data", {})
   133|
   134|    # =========================================================================
   135|    # PRODUCT OPERATIONS
   136|    # =========================================================================
   137|
   138|    def get_products(self, website_id: str, 
   139|                     limit: int = 100) -> List[Dict]:
   140|        """
   141|        Get all products from a Squarespace website.
   142|        
   143|        Args:
   144|            website_id: The Squarespace website ID
   145|            limit: Max products to return (default 100)
   146|            
   147|        Returns:
   148|            List of products with id, name, price, etc.
   149|        """
   150|        offset = 0
   151|        all_products = []
   152|        
   153|        while offset < 1000:  # Max pagination
   154|            def request():
   155|                return requests.get(
   156|                    f"{self.COMMERCE_API}/websites/{website_id}/products",
   157|                    headers=self._get_headers(),
   158|                    params={
   159|                        "limit": min(limit, 100),
   160|                        "offset": offset
   161|                    }
   162|                )
   163|            
   164|            result = self.network.call("squarespace", 600, request)
   165|            
   166|            if not result["success"]:
   167|                break
   168|            
   169|            products = result.get("data", {}).get("products", [])
   170|            if not products:
   171|                break
   172|            
   173|            all_products.extend(products)
   174|            
   175|            if len(products) < limit:
   176|                break
   177|            
   178|            offset += limit
   179|        
   180|        return all_products
   181|
   182|    def get_product(self, website_id: str, product_id: str) -> Optional[Dict]:
   183|        """Get a single product."""
   184|        
   185|        def request():
   186|            return requests.get(
   187|                f"{self.COMMERCE_API}/websites/{website_id}/products/{product_id}",
   188|                headers=self._get_headers()
   189|            )
   190|        
   191|        result = self.network.call("squarespace", 600, request)
   192|        
   193|        if result["success"]:
   194|            return result.get("data", {})
   195|        return None
   196|
   197|    def update_product_price(self, website_id: str, product_id: str,
   198|                            price_cents: int) -> Dict:
   199|        """
   200|        Update product price.
   201|        
   202|        Args:
   203|            website_id: Squarespace website ID
   204|            product_id: Product ID to update
   205|            price_cents: New price in cents (e.g., 2999 for $29.99)
   206|            
   207|        Returns:
   208|            {"success": bool, "message": str}
   209|        """
   210|        # Check idempotency
   211|        identifier = f"{website_id}:{product_id}:{price_cents}"
   212|        if not self.idempotency.check("squarespace", "update_price", identifier):
   213|            return {
   214|                "success": False,
   215|                "error": "Just updated this price. Give me a moment.",
   216|                "recoverable": True
   217|            }
   218|
   219|        def request():
   220|            return requests.patch(
   221|                f"{self.COMMERCE_API}/websites/{website_id}/products/{product_id}",
   222|                headers=self._get_headers(),
   223|                json={
   224|                    "price": {
   225|                        "value": price_cents / 100.0,  # Convert to dollars
   226|                        "currency": "USD"  # Default to USD
   227|                    }
   228|                }
   229|            )
   230|        
   231|        result = self.network.call("squarespace", 600, request)
   232|        
   233|        if result["success"]:
   234|            self.idempotency.log_action(
   235|                "squarespace", "update_product_price", "success",
   236|                {"website_id": website_id, "product_id": product_id, "price": price_cents}
   237|            )
   238|            
   239|            return {
   240|                "success": True,
   241|                "action": "updated",
   242|                "message": f"Updated price to ${price_cents / 100:.2f}"
   243|            }
   244|        
   245|        return {
   246|            "success": False,
   247|            "error": result.get("error", "Failed to update price"),
   248|            "recoverable": True
   249|        }
   250|
   251|    def update_product_inventory(self, website_id: str, product_id: str,
   252|                                 quantity: int) -> Dict:
   253|        """
   254|        Update product inventory (stock) level.
   255|        
   256|        Args:
   257|            website_id: Squarespace website ID
   258|            product_id: Product ID to update
   259|            quantity: New stock quantity (-1 for unlimited)
   260|        """
   261|        def request():
   262|            return requests.patch(
   263|                f"{self.COMMERCE_API}/websites/{website_id}/products/{product_id}",
   264|                headers=self._get_headers(),
   265|                json={
   266|                    "inventory": {
   267|                        "quantity": quantity,
   268|                        "unlimited": quantity < 0
   269|                    }
   270|                }
   271|            )
   272|        
   273|        result = self.network.call("squarespace", 600, request)
   274|        
   275|        if result["success"]:
   276|            return {
   277|                "success": True,
   278|                "action": "updated",
   279|                "message": f"Updated inventory to {quantity if quantity >= 0 else 'unlimited'}"
   280|            }
   281|        
   282|        return {
   283|            "success": False,
   284|            "error": result.get("error", "Failed to update inventory"),
   285|            "recoverable": True
   286|        }
   287|
   288|    # =========================================================================
   289|    # ORDER OPERATIONS
   290|    # =========================================================================
   291|
   292|    def get_orders(self, website_id: str, 
   293|                   status: str = None) -> List[Dict]:
   294|        """
   295|        Get orders from a Squarespace website.
   296|        
   297|        Args:
   298|            website_id: Squarespace website ID
   299|            status: Optional filter (FULFILLED, UNFULFILLED, CANCELLED)
   300|        """
   301|        params = {}
   302|        if status:
   303|            params["status"] = status.upper()
   304|        
   305|        def request():
   306|            return requests.get(
   307|                f"{self.COMMERCE_API}/websites/{website_id}/orders",
   308|                headers=self._get_headers(),
   309|                params=params
   310|            )
   311|        
   312|        result = self.network.call("squarespace", 600, request)
   313|        
   314|        if result["success"]:
   315|            return result.get("data", {}).get("orders", [])
   316|        return []
   317|
   318|    def get_order(self, website_id: str, order_id: str) -> Optional[Dict]:
   319|        """Get a single order."""
   320|        
   321|        def request():
   322|            return requests.get(
   323|                f"{self.COMMERCE_API}/websites/{website_id}/orders/{order_id}",
   324|                headers=self._get_headers()
   325|            )
   326|        
   327|        result = self.network.call("squarespace", 600, request)
   328|        
   329|        if result["success"]:
   330|            return result.get("data", {})
   331|        return None
   332|
   333|    def fulfill_order(self, website_id: str, order_id: str,
   334|                      tracking_number: str = None,
   335|                      carrier: str = None) -> Dict:
   336|        """
   337|        Mark order as fulfilled.
   338|        
   339|        Args:
   340|            website_id: Squarespace website ID
   341|            order_id: Order ID to fulfill
   342|            tracking_number: Optional tracking number
   343|            carrier: Optional carrier (UPS, FEDEX, USPS, etc.)
   344|        """
   345|        def request():
   346|            payload = {"fulfillment": {"status": "FULFILLED"}}
   347|            if tracking_number:
   348|                payload["fulfillment"]["trackingNumber"] = tracking_number
   349|            if carrier:
   350|                payload["fulfillment"]["carrier"] = carrier
   351|                
   352|            return requests.patch(
   353|                f"{self.COMMERCE_API}/websites/{website_id}/orders/{order_id}",
   354|                headers=self._get_headers(),
   355|                json=payload
   356|            )
   357|        
   358|        result = self.network.call("squarespace", 600, request)
   359|        
   360|        if result["success"]:
   361|            return {
   362|                "success": True,
   363|                "action": "fulfilled",
   364|                "message": "Order marked as fulfilled"
   365|            }
   366|        
   367|        return {
   368|            "success": False,
   369|            "error": result.get("error", "Failed to fulfill order"),
   370|            "recoverable": True
   371|        }
   372|
   373|    # =========================================================================
   374|    # INVENTORY SYNC
   375|    # =========================================================================
   376|
   377|    def sync_products_to_database(self, website_id: str) -> Dict:
   378|        """
   379|        Sync all products to local database.
   380|        
   381|        Returns:
   382|            {"success": bool, "synced": count, "message": str}
   383|        """
   384|        products = self.get_products(website_id)
   385|        
   386|        if not products:
   387|            return {
   388|                "success": False,
   389|                "error": "Failed to fetch products"
   390|            }
   391|        
   392|        synced = 0
   393|        with get_db_connection() as conn:
   394|            with conn.cursor() as cur:
   395|                for p in products:
   396|                    # Parse price from Squarespace format
   397|                    price = p.get("price", {})
   398|                    price_cents = int(price.get("value", 0) * 100) if price else 0
   399|                    
   400|                    cur.execute("""
   401|                        INSERT INTO integration_products
   402|                        (user_id, provider, external_id, name, price_cents, metadata)
   403|                        VALUES (%s, %s, %s, %s, %s, %s)
   404|                        ON CONFLICT (user_id, provider, external_id) DO UPDATE SET
   405|                            name = EXCLUDED.name,
   406|                            price_cents = EXCLUDED.price_cents,
   407|                            metadata = EXCLUDED.metadata,
   408|                            updated_at = NOW()
   409|                    """, (
   410|                        self.user_id,
   411|                        "squarespace",
   412|                        p.get("id"),
   413|                        p.get("name"),
   414|                        price_cents,
   415|                        json.dumps(p)
   416|                    ))
   417|                    synced += 1
   418|                
   419|                conn.commit()
   420|        
   421|        self.idempotency.log_action(
   422|            "squarespace", "sync_products", "success",
   423|            {"website_id": website_id, "synced": synced}
   424|        )
   425|        
   426|        return {
   427|            "success": True,
   428|            "synced": synced,
   429|            "message": f"Synced {synced} products from Squarespace"
   430|        }
   431|
   432|    # =========================================================================
   433|    # UTILITY
   434|    # =========================================================================
   435|
   436|    def verify_connection(self) -> Dict:
   437|        """Verify the connection works."""
   438|        if not self.is_connected():
   439|            return {
   440|                "success": False,
   441|                "error": "Not connected to Squarespace"
   442|            }
   443|        
   444|        try:
   445|            websites = self.list_websites()
   446|            return {
   447|                "success": True,
   448|                "websites": len(websites),
   449|                "message": f"Connected! Found {len(websites)} website(s)."
   450|            }
   451|        except Exception as e:
   452|            return {
   453|                "success": False,
   454|                "error": str(e)
   455|            }
   456|
   457|
   458|# Convenience function
   459|def get_adapter(user_id: str) -> SquarespaceAdapter:
   460|    """Get Squarespace adapter instance."""
   461|    return SquarespaceAdapter(user_id)