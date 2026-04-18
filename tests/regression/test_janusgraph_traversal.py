"""
JanusGraph Regression Test — Block 4-I18 Phase 1 Proof Query
============================================================

Tests the cross-user traversal pattern in JanusGraph:
  User A → (similar users via INTERACTED_WITH) → agents those users used

This test is the PASS/FAIL gate for the JanusGraph Phase 1 PR.
It runs in CI via a JanusGraph service container.

Skip conditions:
  - JANUSGRAPH_AVAILABLE != 'true' (set by GitHub Actions service container)
"""

import os
import pytest

JANUSGRAPH_AVAILABLE = os.environ.get('JANUSGRAPH_AVAILABLE', '').lower() == 'true'
JANUSGRAPH_URL = os.environ.get('JANUSGRAPH_URL', 'ws://localhost:8182/gremlin')


@pytest.mark.skipif(not JANUSGRAPH_AVAILABLE, reason="JanusGraph service not available")
def test_janusgraph_cross_user_traversal(api_url):
    """
    Proof-of-concept: cross-user agent traversal.

    Topology:
      u_plumber1 ──[INTERACTED_WITH]── u_plumber2
         │                                 │
       [USES]                           [USES]
         │                                 │
      agent_invoicing                 agent_invoicing

      u_electrician ──[INTERACTED_WITH]── u_electrician2
         │
       [USES]
         │
      agent_hank

    Query: "what agents do users similar to u_plumber1 use?"
    Expected: agent_invoicing (both plumber users are similar)
              agent_hank should NOT appear (electrician is outside depth-2)
    """
    from janusgraph_store import JanusGraphRelationshipStore

    gs = JanusGraphRelationshipStore(janusgraph_url=JANUSGRAPH_URL)

    try:
        # Seed users
        gs.upsert_user('u_plumber1', {'business_type': 'plumber', 'location': 'Columbus'})
        gs.upsert_user('u_plumber2', {'business_type': 'plumber', 'location': 'Columbus'})
        gs.upsert_user('u_electrician', {'business_type': 'electrician', 'location': 'Columbus'})

        # Seed agents
        gs.upsert_agent('agent_invoicing', ['invoicing', 'QB', 'payment'])
        gs.upsert_agent('agent_hank', ['research', 'coding', 'planning'])

        # Relationships: plumber pair are similar, share agent_invoicing
        gs.record_interaction('u_plumber1', 'u_plumber2')
        gs.record_user_uses_agent('u_plumber1', 'agent_invoicing', 'positive')
        gs.record_user_uses_agent('u_plumber2', 'agent_invoicing', 'positive')

        # Electrician uses agent_hank (different cluster)
        gs.record_interaction('u_electrician', 'u_electrician2')
        gs.record_user_uses_agent('u_electrician', 'agent_hank', 'positive')

        # THE QUERY: Find agents used by users similar to plumber1
        similar_agents = gs.find_agents_used_by_similar_users('u_plumber1')

        # Assert plumber cluster agents only
        assert 'agent_invoicing' in similar_agents, \
            f"agent_invoicing should be in similar_agents, got: {similar_agents}"
        assert 'agent_hank' not in similar_agents, \
            f"agent_hank should NOT be in similar_agents (outside depth-2), got: {similar_agents}"

    finally:
        # Cleanup: drop all vertices (edges cascade)
        gs._g.V().drop().iterate()
        gs.close()
