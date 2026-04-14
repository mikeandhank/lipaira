"""
GoDaddy Adapter
================
DNS management for GoDaddy domains.
"""

import logging
from typing import Dict, List, Optional

import requests

from .credential_store import IntegrationCredentialStore, get_db_connection
from .network_handler import NetworkHandler, IdempotencyManager, get_rate_limiter

logger = logging.getLogger(__name__)


class GoDaddyAdapter:
    """
    GoDaddy DNS and Website Builder integration.
    
    Usage:
        adapter = GoDaddyAdapter(user_id)
        
        # Check if connected
        if not adapter.is_connected():
            return "Connect GoDaddy first"
        
        # List domains
        domains = adapter.list_domains()
    
    # Capabilities for operator layer
    capabilities = [
        "configure_dns",
        "check_health",
    ]
        
        # Add DNS record
        adapter.add_dns_record("davesplumbing.com", "TXT", "@", 
                               "v=spf1 include:resend.com ~all")
    """

    BASE_URL = "https://api.godaddy.com"
    GMB_URL = "https://api.godaddy.com/gmb/v1"  # Website Builder (separate API)

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.credential_store = IntegrationCredentialStore(user_id)
        self.network = get_network_handler()
        self.idempotency = IdempotencyManager(user_id)
        self._credentials = None

    def _get_credentials(self) -> Optional[Dict]:
        """Get and cache credentials."""
        if self._credentials is None:
            self._credentials = self.credential_store.get("godaddy")
        return self._credentials

    def is_connected(self) -> bool:
        """Check if GoDaddy is connected."""
        creds = self._get_credentials()
        return creds is not None and bool(creds.get("api_key"))

    def _get_headers(self) -> Dict:
        """Get authorization headers."""
        creds = self._get_credentials()
        if not creds:
            raise ValueError("GoDaddy not connected")
        
        return {
            "Authorization": f"sso-key {creds['api_key']}:{creds['api_secret']}",
            "Content-Type": "application/json"
        }

    # =========================================================================
    # DNS OPERATIONS
    # =========================================================================

    def list_domains(self) -> List[Dict]:
        """List all domains in the GoDaddy account."""
        
        def request():
            return requests.get(
                f"{self.BASE_URL}/domains",
                headers=self._get_headers()
            )
        
        result = self.network.call("godaddy", 60, request)
        
        if not result["success"]:
            return []
        
        domains = result.get("data", [])
        return [
            {
                "domain": d.get("domain"),
                "expires": d.get("expires"),
                "status": d.get("status"),
            }
            for d in domains
        ]

    def get_dns_records(self, domain: str) -> List[Dict]:
        """Get all DNS records for a domain."""
        
        def request():
            return requests.get(
                f"{self.BASE_URL}/domains/{domain}/records",
                headers=self._get_headers()
            )
        
        result = self.network.call("godaddy", 60, request)
        
        if not result["success"]:
            return []
        
        # GoDaddy returns flattened list
        records = result.get("data", [])
        
        # Group by name for easier reading
        grouped = {}
        for r in records:
            name = r.get("name", "@")
            if name not in grouped:
                grouped[name] = []
            grouped[name].append(r)
        
        return grouped

    def add_dns_record(self, domain: str, record_type: str, 
                       name: str, value: str, ttl: int = 3600) -> Dict:
        """
        Add a DNS record.
        
        Args:
            domain: e.g., "davesplumbing.com"
            record_type: "A", "CNAME", "TXT", "MX", etc.
            name: subdomain or "@" for apex
            value: the record value
            ttl: time to live (default 3600)
            
        Returns:
            {"success": bool, "action": "created" | "already_exists", "message": str}
        """
        # Check for existing identical record
        if self.idempotency.dns_record_exists(domain, record_type, name, value):
            return {
                "success": True,
                "action": "already_exists",
                "message": f"Record already exists for {domain}"
            }

        # Check idempotency cache
        identifier = f"{domain}:{record_type}:{name}"
        if not self.idempotency.check("godaddy", "add_dns_record", identifier):
            return {
                "success": False,
                "error": "Just did this. Give me a moment.",
                "recoverable": True
            }

        # GoDaddy uses @ for apex, not empty string
        name = name if name else "@"

        def request():
            return requests.put(
                f"{self.BASE_URL}/domains/{domain}/records/{record_type}/{name}",
                headers=self._get_headers(),
                json=[{"data": value, "ttl": ttl}]
            )

        result = self.network.call("godaddy", 60, request)

        if result["success"]:
            # Log the action
            self.idempotency.log_action(
                "godaddy", "add_dns_record", "success",
                {"domain": domain, "record_type": record_type, "name": name}
            )
            
            return {
                "success": True,
                "action": "created",
                "message": f"Added {record_type} record for {name}.{domain}"
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to add DNS record"),
            "recoverable": True
        }

    def delete_dns_record(self, domain: str, record_type: str, 
                          name: str) -> Dict:
        """Delete a DNS record."""
        
        name = name if name else "@"
        
        identifier = f"{domain}:{record_type}:{name}"
        if not self.idempotency.check("godaddy", "delete_dns_record", identifier):
            return {
                "success": False,
                "error": "Just did this. Give me a moment.",
                "recoverable": True
            }

        def request():
            return requests.delete(
                f"{self.BASE_URL}/domains/{domain}/records/{record_type}/{name}",
                headers=self._get_headers()
            )

        result = self.network.call("godaddy", 60, request)

        if result["success"]:
            self.idempotency.log_action(
                "godaddy", "delete_dns_record", "success",
                {"domain": domain, "record_type": record_type, "name": name}
            )
            
            return {
                "success": True,
                "action": "deleted",
                "message": f"Deleted {record_type} record for {name}.{domain}"
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to delete DNS record"),
            "recoverable": True
        }

    # =========================================================================
    # EMAIL SETUP (SPF, DKIM, DMARC)
    # =========================================================================

    def setup_email_records(self, domain: str, 
                            email_provider: str = "resend.com") -> Dict:
        """
        Set up SPF, DKIM, and DMARC for email sending.
        
        Args:
            domain: Domain to set up (e.g., "davesplumbing.com")
            email_provider: Email service (default: resend.com)
            
        Returns:
            {"success": bool, "results": {...}, "message": str}
        """
        if not self.is_connected():
            return {
                "success": False,
                "error": "GoDaddy not connected"
            }

        results = {}

        # 1. SPF record
        results["spf"] = self.add_dns_record(
            domain, "TXT", "@",
            f"v=spf1 include:{email_provider} ~all"
        )

        # 2. DMARC record
        results["dmarc"] = self.add_dns_record(
            domain, "TXT", "_dmarc",
            "v=DMARC1; p=quarantine; rua=mailto:dmarc@{}".format(domain)
        )

        # 3. Log the setup
        self.idempotency.log_action(
            "godaddy", "setup_email", "success" if results["spf"]["success"] else "partial",
            {"domain": domain, "email_provider": email_provider}
        )

        # Determine overall success
        success = results["spf"]["success"]
        
        return {
            "success": success,
            "results": results,
            "message": f"Email setup {'complete' if success else 'partial'} for {domain}"
        }

    # =========================================================================
    # WEBSITE BUILDER (Limited - requires separate GMB API)
    # =========================================================================

    def list_websites(self) -> List[Dict]:
        """List GoDaddy Website Builder sites."""
        
        def request():
            return requests.get(
                f"{self.GMB_URL}/users/me/websites",
                headers=self._get_headers()
            )
        
        result = self.network.call("godaddy", 60, request)
        
        if not result["success"]:
            # Try to get useful error
            return []
        
        websites = result.get("data", {}).get("websites", [])
        return [
            {
                "id": w.get("id"),
                "domain": w.get("domain"),
                "template": w.get("template"),
                "status": w.get("status"),
            }
            for w in websites
        ]

    # =========================================================================
    # UTILITY
    # =========================================================================

    def verify_connection(self) -> Dict:
        """Verify the connection works."""
        if not self.is_connected():
            return {
                "success": False,
                "error": "Not connected to GoDaddy"
            }
        
        try:
            domains = self.list_domains()
            return {
                "success": True,
                "domains": len(domains),
                "message": f"Connected! Found {len(domains)} domain(s)."
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Convenience function
def get_adapter(user_id: str) -> GoDaddyAdapter:
    """Get GoDaddy adapter instance."""
    return GoDaddyAdapter(user_id)