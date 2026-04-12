# feel free to ignore this comment
     1|"""
     2|Shopify Adapter
     3|===============
     4|Shopify Admin API integration for e-commerce management.
     5|
     6|Shopify uses access tokens (not OAuth) - client needs to generate from their store.
     7|"""
     8|
     9|import os
    10|import json
    11|import logging
    12|import requests
    13|from typing import Dict, List, Optional, Any
    14|from urllib.parse import urljoin
    15|
    16|logger = logging.getLogger(__name__)
    17|
    18|# Shopify API base
    19|SHOPIFY_API_VERSION = "2024-01"
    20|
    21|
    22|class ShopifyAdapter:
    23|    """Adapter for Shopify Admin API."""
    24|    
    25|    # Capabilities for operator layer
    26|    capabilities = [
    27|        "update_prices",
    28|        "update_inventory",
    29|        "fulfill_orders",
    30|        "sync_products",
    31|        "check_health",
    32|        "query",
    33|    ]
    34|
    35|    def __init__(self, user_id: str):
    36|        self.user_id = user_id
    37|        self.credentials = None
    38|        self._load_credentials()
    39|
    40|    def _load_credentials(self):
    41|        """Load credentials from credential store."""
    42|        from .credential_store import IntegrationCredentialStore
    43|        store = IntegrationCredentialStore(self.user_id)
    44|        self.credentials = store.get("shopify")
    45|
    46|    def is_connected(self) -> bool:
    47|        """Check if connected to Shopify."""
    48|        return self.credentials is not None and bool(
    49|            self.credentials.get("access_token") and self.credentials.get("shop_domain")
    50|        )
    51|
    52|    def _get_headers(self) -> Dict[str, str]:
    53|        """Get API headers with access token."""
    54|        return {
    55|            "X-Shopify-Access-Token": self.credentials["access_token"],
    56|            "Content-Type": "application/json",
    57|        }
    58|
    59|    def _api_url(self, path: str) -> str:
    60|        """Build full API URL."""
    61|        shop_domain = self.credentials["shop_domain"]
    62|        # Ensure shop_domain doesn't have protocol
    63|        shop_domain = shop_domain.replace("https://", "").replace("http://", "").rstrip("/")
    64|        base_url = f"https://{shop_domain}/admin/api/{SHOPIFY_API_VERSION}"
    65|        return urljoin(base_url, path.lstrip("/"))
    66|
    67|    def verify_connection(self) -> Dict[str, Any]:
    68|        """
    69|        Verify Shopify connection by fetching shop info.
    70|        
    71|        Returns:
    72|            {"success": bool, "shop": dict, "message": str, "products_count": int}
    73|        """
    74|        if not self.is_connected():
    75|            return {"success": False, "error": "Not connected to Shopify"}
    76|
    77|        try:
    78|            response = requests.get(
    79|                self._api_url("/shop.json"),
    80|                headers=self._get_headers(),
    81|                timeout=30
    82|            )
    83|
    84|            if response.status_code != 200:
    85|                return {
    86|                    "success": False,
    87|                    "error": f"API error: {response.status_code}"
    88|                }
    89|
    90|            shop = response.json().get("shop", {})
    91|            
    92|            # Get product count
    93|            products_response = requests.get(
    94|                self._api_url("/products/count.json"),
    95|                headers=self._get_headers(),
    96|                timeout=30
    97|            )
    98|            products_count = products_response.json().get("count", 0) if products_response.status_code == 200 else 0
    99|
   100|            return {
   101|                "success": True,
   102|                "shop": {
   103|                    "name": shop.get("name"),
   104|                    "domain": shop.get("domain"),
   105|                    "email": shop.get("email"),
   106|                    "plan": shop.get("plan_display_name"),
   107|                },
   108|                "message": f"Connected to {shop.get('name')}",
   109|                "products_count": products_count,
   110|            }
   111|
   112|        except requests.RequestException as e:
   113|            logger.error(f"Shopify connection error: {e}")
   114|            return {"success": False, "error": str(e)}
   115|
   116|    def list_products(self, limit: int = 50, status: str = "active") -> List[Dict]:
   117|        """
   118|        List products from Shopify store.
   119|        
   120|        Args:
   121|            limit: Max products to fetch (max 250)
   122|            status: Filter by status (any, active, archived, draft)
   123|            
   124|        Returns:
   125|            List of product dictionaries
   126|        """
   127|        if not self.is_connected():
   128|            return []
   129|
   130|        try:
   131|            response = requests.get(
   132|                self._api_url(f"/products.json?limit={min(limit, 250)}&status={status}"),
   133|                headers=self._get_headers(),
   134|                timeout=30
   135|            )
   136|
   137|            if response.status_code != 200:
   138|                logger.error(f"Shopify products error: {response.status_code}")
   139|                return []
   140|
   141|            return response.json().get("products", [])
   142|
   143|        except requests.RequestException as e:
   144|            logger.error(f"Shopify API error: {e}")
   145|            return []
   146|
   147|    def get_product(self, product_id: int) -> Optional[Dict]:
   148|        """Get single product by ID."""
   149|        if not self.is_connected():
   150|            return None
   151|
   152|        try:
   153|            response = requests.get(
   154|                self._api_url(f"/products/{product_id}.json"),
   155|                headers=self._get_headers(),
   156|                timeout=30
   157|            )
   158|
   159|            if response.status_code == 200:
   160|                return response.json().get("product")
   161|            return None
   162|
   163|        except requests.RequestException as e:
   164|            logger.error(f"Shopify API error: {e}")
   165|            return None
   166|
   167|    def update_product_price(self, product_id: int, price: float) -> Dict[str, Any]:
   168|        """
   169|        Update product price (variants).
   170|        
   171|        Args:
   172|            product_id: Shopify product ID
   173|            price: New price in USD
   174|            
   175|        Returns:
   176|            {"success": bool, "product": dict}
   177|        """
   178|        if not self.is_connected():
   179|            return {"success": False, "error": "Not connected"}
   180|
   181|        product = self.get_product(product_id)
   182|        if not product:
   183|            return {"success": False, "error": "Product not found"}
   184|
   185|        # Update all variants with new price
   186|        variants = product.get("variants", [])
   187|        variant_ids = [v["id"] for v in variants]
   188|
   189|        if not variant_ids:
   190|            return {"success": False, "error": "No variants found"}
   191|
   192|        try:
   193|            # Shopify requires updating via inventory item or variant
   194|            # Simplest: update each variant's price
   195|            for variant_id in variant_ids:
   196|                response = requests.put(
   197|                    self._api_url(f"/variants/{variant_id}.json"),
   198|                    headers=self._get_headers(),
   199|                    json={
   200|                        "variant": {
   201|                            "id": variant_id,
   202|                            "price": f"{price:.2f}"
   203|                        }
   204|                    },
   205|                    timeout=30
   206|                )
   207|
   208|                if response.status_code != 200:
   209|                    return {"success": False, "error": f"Failed to update variant {variant_id}"}
   210|
   211|            return {
   212|                "success": True,
   213|                "message": f"Updated price to ${price:.2f} for {len(variant_ids)} variant(s)"
   214|            }
   215|
   216|        except requests.RequestException as e:
   217|            logger.error(f"Shopify price update error: {e}")
   218|            return {"success": False, "error": str(e)}
   219|
   220|    def update_inventory(self, inventory_item_id: int, quantity: int, location_id: int = None) -> Dict[str, Any]:
   221|        """
   222|        Update inventory level for a product variant.
   223|        
   224|        Args:
   225|            inventory_item_id: Shopify inventory_item_id (from variant)
   226|            quantity: New quantity (-1 for unlimited)
   227|            location_id: Required for inventory updates
   228|            
   229|        Returns:
   230|            {"success": bool}
   231|        """
   232|        if not self.is_connected():
   233|            return {"success": False, "error": "Not connected"}
   234|
   235|        if not location_id:
   236|            # Get default location
   237|            location_id = self._get_default_location()
   238|            if not location_id:
   239|                return {"success": False, "error": "No location found. Provide location_id."}
   240|
   241|        try:
   242|            # Set inventory level
   243|            response = requests.post(
   244|                self._api_url("/inventory_levels/set.json"),
   245|                headers=self._get_headers(),
   246|                json={
   247|                    "location_id": location_id,
   248|                    "inventory_item_id": inventory_item_id,
   249|                    "available": quantity if quantity >= 0 else 0,
   250|                },
   251|                timeout=30
   252|            )
   253|
   254|            if response.status_code != 200:
   255|                return {"success": False, "error": f"API error: {response.status_code}"}
   256|
   257|            return {
   258|                "success": True,
   259|                "message": f"Updated inventory to {quantity}"
   260|            }
   261|
   262|        except requests.RequestException as e:
   263|            logger.error(f"Shopify inventory update error: {e}")
   264|            return {"success": False, "error": str(e)}
   265|
   266|    def _get_default_location(self) -> Optional[int]:
   267|        """Get the first inventory location ID."""
   268|        try:
   269|            response = requests.get(
   270|                self._api_url("/locations.json"),
   271|                headers=self._get_headers(),
   272|                timeout=30
   273|            )
   274|
   275|            if response.status_code == 200:
   276|                locations = response.json().get("locations", [])
   277|                if locations:
   278|                    return locations[0]["id"]
   279|        except:
   280|            pass
   281|        return None
   282|
   283|    def list_orders(self, status: str = "any", limit: int = 50) -> List[Dict]:
   284|        """
   285|        List orders from Shopify.
   286|        
   287|        Args:
   288|            status: Filter (any, open, closed, cancelled)
   289|            limit: Max orders (max 250)
   290|            
   291|        Returns:
   292|            List of order dictionaries
   293|        """
   294|        if not self.is_connected():
   295|            return []
   296|
   297|        try:
   298|            response = requests.get(
   299|                self._api_url(f"/orders.json?status={status}&limit={min(limit, 250)}"),
   300|                headers=self._get_headers(),
   301|                timeout=30
   302|            )
   303|
   304|            if response.status_code != 200:
   305|                logger.error(f"Shopify orders error: {response.status_code}")
   306|                return []
   307|
   308|            return response.json().get("orders", [])
   309|
   310|        except requests.RequestException as e:
   311|            logger.error(f"Shopify API error: {e}")
   312|            return []
   313|
   314|    def get_order(self, order_id: int) -> Optional[Dict]:
   315|        """Get single order by ID."""
   316|        if not self.is_connected():
   317|            return None
   318|
   319|        try:
   320|            response = requests.get(
   321|                self._api_url(f"/orders/{order_id}.json"),
   322|                headers=self._get_headers(),
   323|                timeout=30
   324|            )
   325|
   326|            if response.status_code == 200:
   327|                return response.json().get("order")
   328|            return None
   329|
   330|        except requests.RequestException as e:
   331|            logger.error(f"Shopify API error: {e}")
   332|            return None
   333|
   334|    def fulfill_order(self, order_id: int, tracking_number: str = None, 
   335|                      tracking_company: str = None, notify_customer: bool = True) -> Dict[str, Any]:
   336|        """
   337|        Fulfill an order (or part of an order).
   338|        
   339|        Args:
   340|            order_id: Shopify order ID
   341|            tracking_number: Optional tracking number
   342|            tracking_company: Carrier (ups, fedex, usps, dhl, etc.)
   343|            notify_customer: Send notification to customer
   344|            
   345|        Returns:
   346|            {"success": bool, "fulfillment": dict}
   347|        """
   348|        if not self.is_connected():
   349|            return {"success": False, "error": "Not connected"}
   350|
   351|        order = self.get_order(order_id)
   352|        if not order:
   353|            return {"success": False, "error": "Order not found"}
   354|
   355|        # Check if already fulfilled
   356|        if order.get("fulfillment_status") == "fulfilled":
   357|            return {"success": False, "error": "Order already fulfilled"}
   358|
   359|        # Get line items that need fulfillment
   360|        line_items = order.get("line_items", [])
   361|        
   362|        # Build fulfillment payload
   363|        fulfillment = {
   364|            "location_id": self._get_default_location(),
   365|            "notify": notify_customer,
   366|        }
   367|
   368|        if tracking_number:
   369|            fulfillment["tracking_numbers"] = [tracking_number]
   370|        if tracking_company:
   371|            fulfillment["tracking_company"] = tracking_company
   372|
   373|        try:
   374|            response = requests.post(
   375|                self._api_url(f"/orders/{order_id}/fulfillments.json"),
   376|                headers=self._get_headers(),
   377|                json={"fulfillment": fulfillment},
   378|                timeout=30
   379|            )
   380|
   381|            if response.status_code != 201 and response.status_code != 200:
   382|                return {"success": False, "error": f"API error: {response.status_code}"}
   383|
   384|            return {
   385|                "success": True,
   386|                "message": "Order fulfilled successfully",
   387|                "fulfillment": response.json().get("fulfillment", {})
   388|            }
   389|
   390|        except requests.RequestException as e:
   391|            logger.error(f"Shopify fulfillment error: {e}")
   392|            return {"success": False, "error": str(e)}
   393|
   394|    def create_fulfillment(self, order_id: int, line_items: List[Dict],
   395|                          tracking_number: str = None, tracking_company: str = None) -> Dict[str, Any]:
   396|        """
   397|        Create partial fulfillment for specific line items.
   398|        
   399|        Args:
   400|            order_id: Shopify order ID
   401|            line_items: [{"id": line_item_id, "quantity": 2}]
   402|            tracking_number: Optional tracking
   403|            tracking_company: Carrier
   404|            
   405|        Returns:
   406|            {"success": bool}
   407|        """
   408|        if not self.is_connected():
   409|            return {"success": False, "error": "Not connected"}
   410|
   411|        fulfillment = {
   412|            "location_id": self._get_default_location(),
   413|            "line_items": line_items,
   414|        }
   415|
   416|        if tracking_number:
   417|            fulfillment["tracking_numbers"] = [tracking_number]
   418|        if tracking_company:
   419|            fulfillment["tracking_company"] = tracking_company
   420|
   421|        try:
   422|            response = requests.post(
   423|                self._api_url(f"/orders/{order_id}/fulfillments.json"),
   424|                headers=self._get_headers(),
   425|                json={"fulfillment": fulfillment},
   426|                timeout=30
   427|            )
   428|
   429|            if response.status_code not in (200, 201):
   430|                return {"success": False, "error": f"API error: {response.status_code}"}
   431|
   432|            return {"success": True, "message": "Partial fulfillment created"}
   433|
   434|        except requests.RequestException as e:
   435|            logger.error(f"Shopify fulfillment error: {e}")
   436|            return {"success": False, "error": str(e)}
   437|
   438|    def update_inventory_bulk(self, updates: List[Dict]) -> Dict[str, Any]:
   439|        """
   440|        Bulk update inventory levels.
   441|        
   442|        Args:
   443|            updates: [{"inventory_item_id": int, "quantity": int, "location_id": int}]
   444|            
   445|        Returns:
   446|            {"success": bool, "updated": int, "failed": int}
   447|        """
   448|        if not self.is_connected():
   449|            return {"success": False, "error": "Not connected"}
   450|
   451|        updated = 0
   452|        failed = 0
   453|
   454|        for update in updates:
   455|            result = self.update_inventory(
   456|                update["inventory_item_id"],
   457|                update["quantity"],
   458|                update.get("location_id")
   459|            )
   460|            if result["success"]:
   461|                updated += 1
   462|            else:
   463|                failed += 1
   464|
   465|        return {
   466|            "success": failed == 0,
   467|            "updated": updated,
   468|            "failed": failed
   469|        }
   470|
   471|    def sync_products_to_database(self) -> Dict[str, Any]:
   472|        """
   473|        Sync all products to local database table.
   474|        
   475|        Creates/updates `shopify_products` table.
   476|        """
   477|        if not self.is_connected():
   478|            return {"success": False, "error": "Not connected"}
   479|
   480|        import psycopg2
   481|        from psycopg2.extras import execute_values
   482|        import os
   483|        from urllib.parse import urlparse
   484|
   485|        db_url = os.environ.get("DATABASE_URL")
   486|        if not db_url:
   487|            return {"success": False, "error": "DATABASE_URL not set"}
   488|
   489|        result = urlparse(db_url)
   490|        
   491|        try:
   492|            conn = psycopg2.connect(
   493|                host=result.hostname,
   494|                port=result.port or 5432,
   495|                database=result.path.lstrip("/"),
   496|                user=result.username,
   497|                password=result.password
   498|            )
   499|        except Exception as e:
   500|            return {"success": False, "error": f"DB connection failed: {e}"}
   501|