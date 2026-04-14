"""Memory store skill — explicitly stores a fact to the user's memory graph."""

import os
import uuid
import logging
import psycopg2
from skills.registry import BaseSkill

log = logging.getLogger(__name__)


class MemoryStoreSkill(BaseSkill):
    name = "memory_store"
    description = "Store an important fact, preference, or context to long-term memory"
    required_integrations = []

    def execute(self, params, user_id, business_id=None):
        content = params.get("content")
        if not content:
            raise ValueError("'content' parameter required")

        node_type = params.get("type", "fact")
        confidence = float(params.get("confidence", 0.85))
        source = params.get("source", "explicit")

        conn = None
        try:
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            node_id = str(uuid.uuid4())

            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO memory_nodes
                    (id, user_id, node_type, content, confidence, source, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT DO NOTHING
                """, (node_id, user_id, node_type, content, confidence, source))
                conn.commit()

            # Generate embedding (non-fatal if it fails)
            try:
                from memory_embeddings import store_embedding
                store_embedding(node_id, user_id, content, conn)
            except Exception as e:
                log.warning(f"[memory_store] embedding skipped: {e}")

            log.info(f"[memory_store] stored node {node_id} for user {user_id}")
            return {"stored": True, "node_id": node_id, "content": content}

        except Exception as e:
            log.warning(f"[memory_store] failed: {e}")
            raise
        finally:
            if conn:
                conn.close()