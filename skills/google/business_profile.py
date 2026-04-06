"""Google Business Profile skill."""

from skills.registry import BaseSkill
from skills.base import get_integration_tokens


class GoogleBusinessUpdateSkill(BaseSkill):
    """Update Google Business profile."""
    name = "google_business_update"
    description = "Update Google Business profile info"
    required_integrations = ["google_business"]
    
    def execute(self, params, user_id, business_id=None):
        tokens = get_integration_tokens(user_id, business_id, "google")
        return {"success": False, "note": "Not implemented"}