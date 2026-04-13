"""Memory skills package for Lipaira.

Provides skills for storing and recalling user memory:
- MemoryStoreSkill: Store facts, preferences, and context to long-term memory
- MemoryRecallSkill: Query user's memory graph

Key functions/classes:
    MemoryRecallSkill: Queries user's memory graph (placeholder - not implemented)
    MemoryStoreSkill: Stores nodes in memory_nodes table with embeddings
"""

from skills.registry import BaseSkill


class MemoryRecallSkill(BaseSkill):
    """Recall memories from user's memory graph."""
    name = "memory_recall"
    description = "Query user's memory graph"
    required_integrations = []
    execution_tier = "free"  # Read-only: free tier allowed
    
    def execute(self, params, user_id, business_id=None):
        return {"results": [], "note": "Not implemented"}

