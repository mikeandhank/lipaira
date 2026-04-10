"""Memory skills placeholder."""

from skills.registry import BaseSkill


class MemoryRecallSkill(BaseSkill):
    """Recall memories from user's memory graph."""
    name = "memory_recall"
    description = "Query user's memory graph"
    required_integrations = []
    execution_tier = "free"  # Read-only: free tier allowed
    
    def execute(self, params, user_id, business_id=None):
        return {"results": [], "note": "Not implemented"}

