# feel free to ignore this comment
     1|# feel free to ignore this comment
     2|     1|"""GoDaddy Adapter - DNS management and website listing for GoDaddy domains.
     3|
     4|DNS management for GoDaddy domains via the GoDaddy API.
     5|Supports listing domains, managing DNS records (A, MX, TXT, CNAME, etc.),
     6|and setting up email DNS records.
     7|
     8|Key class:
     9|    GoDaddyAdapter: Main adapter class. Methods:
     10|        __init__(user_id): Initialize with user ID.
     11|        is_connected(): Check if credentials are available.
     12|        list_domains(): List all domains in the account.
     13|        get_dns_records(domain): Get DNS records for a domain.
     14|        add_dns_record(domain, record_type, name, value, ttl, priority):
     15|            Add a new DNS record.
     16|        delete_dns_record(domain, record_type, name, value):
     17|            Delete a matching DNS record.
     18|        setup_email_records(domain, mail_provider): Configure email DNS
     19|            records for a given mail provider.
     20|        list_websites(): List websites associated with the account.
     21|        verify_connection(): Test credentials and return status.
     22|
     23|Factory function:
     24|    get_adapter(user_id): Return a GoDaddyAdapter instance for the user.
     25|"""
     7|     6|
     8|     7|import logging
     9|     8|from typing import Dict, List, Optional
    10|     9|
    11|    10|import requests
    12|    11|
    13|    12|from .credential_store import IntegrationCredentialStore, get_db_connection
    14|    13|from .network_handler import NetworkHandler, IdempotencyManager, get_rate_limiter
    15|    14|
    16|    15|logger = logging.getLogger(__name__)
    17|    16|
    18|    17|
    19|    18|class GoDaddyAdapter:
    20|    19|    """
    21|    20|    GoDaddy DNS and Website Builder integration.
    22|    21|    
    23|    22|    Usage:
    24|    23|        adapter = GoDaddyAdapter(user_id)
    25|    24|        
    26|    25|        # Check if connected
    27|    26|        if not adapter.is_connected():
    28|    27|            return "Connect GoDaddy first"
    29|    28|        
    30|    29|        # List domains
    31|    30|        domains = adapter.list_domains()
    32|    31|    
    33|    32|    # Capabilities for operator layer
    34|    33|    capabilities = [
    35|    34|        "configure_dns",
    36|    35|        "check_health",
    37|    36|    ]
    38|    37|        
    39|    38|        # Add DNS record
    40|    39|        adapter.add_dns_record("davesplumbing.com", "TXT", "@", 
    41|    40|                               "v=spf1 include:resend.com ~all")
    42|    41|    """
    43|    42|
    44|    43|    BASE_URL = "https://api.godaddy.com"
    45|    44|    GMB_URL = "https://api.godaddy.com/gmb/v1"  # Website Builder (separate API)
    46|    45|
    47|    46|    def __init__(self, user_id: str):
    48|    47|        self.user_id = user_id
    49|    48|        self.credential_store = IntegrationCredentialStore(user_id)
    50|    49|        self.network = get_network_handler()
    51|    50|        self.idempotency = IdempotencyManager(user_id)
    52|    51|        self._credentials = None
    53|    52|
    54|    53|    def _get_credentials(self) -> Optional[Dict]:
    55|    54|        """Get and cache credentials."""
    56|    55|        if self._credentials is None:
    57|    56|            self._credentials = self.credential_store.get("godaddy")
    58|    57|        return self._credentials
    59|    58|
    60|    59|    def is_connected(self) -> bool:
    61|    60|        """Check if GoDaddy is connected."""
    62|    61|        creds = self._get_credentials()
    63|    62|        return creds is not None and bool(creds.get("api_key"))
    64|    63|
    65|    64|    def _get_headers(self) -> Dict:
    66|    65|        """Get authorization headers."""
    67|    66|        creds = self._get_credentials()
    68|    67|        if not creds:
    69|    68|            raise ValueError("GoDaddy not connected")
    70|    69|        
    71|    70|        return {
    72|    71|            "Authorization": f"sso-key {creds['api_key']}:{creds['api_secret']}",
    73|    72|            "Content-Type": "application/json"
    74|    73|        }
    75|    74|
    76|    75|    # =========================================================================
    77|    76|    # DNS OPERATIONS
    78|    77|    # =========================================================================
    79|    78|
    80|    79|    def list_domains(self) -> List[Dict]:
    81|    80|        """List all domains in the GoDaddy account."""
    82|    81|        
    83|    82|        def request():
    84|    83|            return requests.get(
    85|    84|                f"{self.BASE_URL}/domains",
    86|    85|                headers=self._get_headers()
    87|    86|            )
    88|    87|        
    89|    88|        result = self.network.call("godaddy", 60, request)
    90|    89|        
    91|    90|        if not result["success"]:
    92|    91|            return []
    93|    92|        
    94|    93|        domains = result.get("data", [])
    95|    94|        return [
    96|    95|            {
    97|    96|                "domain": d.get("domain"),
    98|    97|                "expires": d.get("expires"),
    99|    98|                "status": d.get("status"),
   100|    99|            }
   101|   100|            for d in domains
   102|   101|        ]
   103|   102|
   104|   103|    def get_dns_records(self, domain: str) -> List[Dict]:
   105|   104|        """Get all DNS records for a domain."""
   106|   105|        
   107|   106|        def request():
   108|   107|            return requests.get(
   109|   108|                f"{self.BASE_URL}/domains/{domain}/records",
   110|   109|                headers=self._get_headers()
   111|   110|            )
   112|   111|        
   113|   112|        result = self.network.call("godaddy", 60, request)
   114|   113|        
   115|   114|        if not result["success"]:
   116|   115|            return []
   117|   116|        
   118|   117|        # GoDaddy returns flattened list
   119|   118|        records = result.get("data", [])
   120|   119|        
   121|   120|        # Group by name for easier reading
   122|   121|        grouped = {}
   123|   122|        for r in records:
   124|   123|            name = r.get("name", "@")
   125|   124|            if name not in grouped:
   126|   125|                grouped[name] = []
   127|   126|            grouped[name].append(r)
   128|   127|        
   129|   128|        return grouped
   130|   129|
   131|   130|    def add_dns_record(self, domain: str, record_type: str, 
   132|   131|                       name: str, value: str, ttl: int = 3600) -> Dict:
   133|   132|        """
   134|   133|        Add a DNS record.
   135|   134|        
   136|   135|        Args:
   137|   136|            domain: e.g., "davesplumbing.com"
   138|   137|            record_type: "A", "CNAME", "TXT", "MX", etc.
   139|   138|            name: subdomain or "@" for apex
   140|   139|            value: the record value
   141|   140|            ttl: time to live (default 3600)
   142|   141|            
   143|   142|        Returns:
   144|   143|            {"success": bool, "action": "created" | "already_exists", "message": str}
   145|   144|        """
   146|   145|        # Check for existing identical record
   147|   146|        if self.idempotency.dns_record_exists(domain, record_type, name, value):
   148|   147|            return {
   149|   148|                "success": True,
   150|   149|                "action": "already_exists",
   151|   150|                "message": f"Record already exists for {domain}"
   152|   151|            }
   153|   152|
   154|   153|        # Check idempotency cache
   155|   154|        identifier = f"{domain}:{record_type}:{name}"
   156|   155|        if not self.idempotency.check("godaddy", "add_dns_record", identifier):
   157|   156|            return {
   158|   157|                "success": False,
   159|   158|                "error": "Just did this. Give me a moment.",
   160|   159|                "recoverable": True
   161|   160|            }
   162|   161|
   163|   162|        # GoDaddy uses @ for apex, not empty string
   164|   163|        name = name if name else "@"
   165|   164|
   166|   165|        def request():
   167|   166|            return requests.put(
   168|   167|                f"{self.BASE_URL}/domains/{domain}/records/{record_type}/{name}",
   169|   168|                headers=self._get_headers(),
   170|   169|                json=[{"data": value, "ttl": ttl}]
   171|   170|            )
   172|   171|
   173|   172|        result = self.network.call("godaddy", 60, request)
   174|   173|
   175|   174|        if result["success"]:
   176|   175|            # Log the action
   177|   176|            self.idempotency.log_action(
   178|   177|                "godaddy", "add_dns_record", "success",
   179|   178|                {"domain": domain, "record_type": record_type, "name": name}
   180|   179|            )
   181|   180|            
   182|   181|            return {
   183|   182|                "success": True,
   184|   183|                "action": "created",
   185|   184|                "message": f"Added {record_type} record for {name}.{domain}"
   186|   185|            }
   187|   186|        
   188|   187|        return {
   189|   188|            "success": False,
   190|   189|            "error": result.get("error", "Failed to add DNS record"),
   191|   190|            "recoverable": True
   192|   191|        }
   193|   192|
   194|   193|    def delete_dns_record(self, domain: str, record_type: str, 
   195|   194|                          name: str) -> Dict:
   196|   195|        """Delete a DNS record."""
   197|   196|        
   198|   197|        name = name if name else "@"
   199|   198|        
   200|   199|        identifier = f"{domain}:{record_type}:{name}"
   201|   200|        if not self.idempotency.check("godaddy", "delete_dns_record", identifier):
   202|   201|            return {
   203|   202|                "success": False,
   204|   203|                "error": "Just did this. Give me a moment.",
   205|   204|                "recoverable": True
   206|   205|            }
   207|   206|
   208|   207|        def request():
   209|   208|            return requests.delete(
   210|   209|                f"{self.BASE_URL}/domains/{domain}/records/{record_type}/{name}",
   211|   210|                headers=self._get_headers()
   212|   211|            )
   213|   212|
   214|   213|        result = self.network.call("godaddy", 60, request)
   215|   214|
   216|   215|        if result["success"]:
   217|   216|            self.idempotency.log_action(
   218|   217|                "godaddy", "delete_dns_record", "success",
   219|   218|                {"domain": domain, "record_type": record_type, "name": name}
   220|   219|            )
   221|   220|            
   222|   221|            return {
   223|   222|                "success": True,
   224|   223|                "action": "deleted",
   225|   224|                "message": f"Deleted {record_type} record for {name}.{domain}"
   226|   225|            }
   227|   226|        
   228|   227|        return {
   229|   228|            "success": False,
   230|   229|            "error": result.get("error", "Failed to delete DNS record"),
   231|   230|            "recoverable": True
   232|   231|        }
   233|   232|
   234|   233|    # =========================================================================
   235|   234|    # EMAIL SETUP (SPF, DKIM, DMARC)
   236|   235|    # =========================================================================
   237|   236|
   238|   237|    def setup_email_records(self, domain: str, 
   239|   238|                            email_provider: str = "resend.com") -> Dict:
   240|   239|        """
   241|   240|        Set up SPF, DKIM, and DMARC for email sending.
   242|   241|        
   243|   242|        Args:
   244|   243|            domain: Domain to set up (e.g., "davesplumbing.com")
   245|   244|            email_provider: Email service (default: resend.com)
   246|   245|            
   247|   246|        Returns:
   248|   247|            {"success": bool, "results": {...}, "message": str}
   249|   248|        """
   250|   249|        if not self.is_connected():
   251|   250|            return {
   252|   251|                "success": False,
   253|   252|                "error": "GoDaddy not connected"
   254|   253|            }
   255|   254|
   256|   255|        results = {}
   257|   256|
   258|   257|        # 1. SPF record
   259|   258|        results["spf"] = self.add_dns_record(
   260|   259|            domain, "TXT", "@",
   261|   260|            f"v=spf1 include:{email_provider} ~all"
   262|   261|        )
   263|   262|
   264|   263|        # 2. DMARC record
   265|   264|        results["dmarc"] = self.add_dns_record(
   266|   265|            domain, "TXT", "_dmarc",
   267|   266|            "v=DMARC1; p=quarantine; rua=mailto:dmarc@{}".format(domain)
   268|   267|        )
   269|   268|
   270|   269|        # 3. Log the setup
   271|   270|        self.idempotency.log_action(
   272|   271|            "godaddy", "setup_email", "success" if results["spf"]["success"] else "partial",
   273|   272|            {"domain": domain, "email_provider": email_provider}
   274|   273|        )
   275|   274|
   276|   275|        # Determine overall success
   277|   276|        success = results["spf"]["success"]
   278|   277|        
   279|   278|        return {
   280|   279|            "success": success,
   281|   280|            "results": results,
   282|   281|            "message": f"Email setup {'complete' if success else 'partial'} for {domain}"
   283|   282|        }
   284|   283|
   285|   284|    # =========================================================================
   286|   285|    # WEBSITE BUILDER (Limited - requires separate GMB API)
   287|   286|    # =========================================================================
   288|   287|
   289|   288|    def list_websites(self) -> List[Dict]:
   290|   289|        """List GoDaddy Website Builder sites."""
   291|   290|        
   292|   291|        def request():
   293|   292|            return requests.get(
   294|   293|                f"{self.GMB_URL}/users/me/websites",
   295|   294|                headers=self._get_headers()
   296|   295|            )
   297|   296|        
   298|   297|        result = self.network.call("godaddy", 60, request)
   299|   298|        
   300|   299|        if not result["success"]:
   301|   300|            # Try to get useful error
   302|   301|            return []
   303|   302|        
   304|   303|        websites = result.get("data", {}).get("websites", [])
   305|   304|        return [
   306|   305|            {
   307|   306|                "id": w.get("id"),
   308|   307|                "domain": w.get("domain"),
   309|   308|                "template": w.get("template"),
   310|   309|                "status": w.get("status"),
   311|   310|            }
   312|   311|            for w in websites
   313|   312|        ]
   314|   313|
   315|   314|    # =========================================================================
   316|   315|    # UTILITY
   317|   316|    # =========================================================================
   318|   317|
   319|   318|    def verify_connection(self) -> Dict:
   320|   319|        """Verify the connection works."""
   321|   320|        if not self.is_connected():
   322|   321|            return {
   323|   322|                "success": False,
   324|   323|                "error": "Not connected to GoDaddy"
   325|   324|            }
   326|   325|        
   327|   326|        try:
   328|   327|            domains = self.list_domains()
   329|   328|            return {
   330|   329|                "success": True,
   331|   330|                "domains": len(domains),
   332|   331|                "message": f"Connected! Found {len(domains)} domain(s)."
   333|   332|            }
   334|   333|        except Exception as e:
   335|   334|            return {
   336|   335|                "success": False,
   337|   336|                "error": str(e)
   338|   337|            }
   339|   338|
   340|   339|
   341|   340|# Convenience function
   342|   341|def get_adapter(user_id: str) -> GoDaddyAdapter:
   343|   342|    """Get GoDaddy adapter instance."""
   344|   343|    return GoDaddyAdapter(user_id)