import os
import logging
import requests

log = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


def generate_embedding(text: str) -> list | None:
    """
    Generate embedding via OpenAI text-embedding-3-small.
    Cost: ~$0.000001 per memory — essentially free.
    Uses OPENAI_API_KEY if set, otherwise skips silently.
    """
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        log.warning("No OPENAI_API_KEY — embeddings disabled")
        return None

    try:
        resp = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": EMBEDDING_MODEL,
                "input": text[:8000]  # cap at 8k chars
            },
            timeout=10
        )
        if resp.ok:
            return resp.json()["data"][0]["embedding"]
        else:
            log.warning(f"Embedding API error: {resp.status_code}")
            return None
    except Exception as e:
        log.warning(f"Embedding generation failed: {e}")
        return None


def store_embedding(node_id: str, user_id: str, text: str, conn) -> bool:
    """
    Generate and store embedding for a memory node.
    Called in background after memory_store.
    conn: existing psycopg2 connection
    """
    embedding = generate_embedding(text)
    if not embedding:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO memory_embeddings
                (node_id, user_id, embedding)
                VALUES (%s, %s, %s::vector)
                ON CONFLICT (node_id, user_id)
                DO UPDATE SET embedding = EXCLUDED.embedding
            """, (node_id, user_id, str(embedding)))
            conn.commit()
        return True
    except Exception as e:
        log.warning(f"store_embedding failed: {e}")
        return False


def recall_by_embedding(query: str, user_id: str, conn, limit: int = 8, threshold: float = 0.7) -> list:
    """
    Find memory nodes semantically similar to query.
    Returns list of (content, similarity_score) tuples.
    Falls back to empty list if embeddings unavailable.
    """
    query_embedding = generate_embedding(query)
    if not query_embedding:
        return []

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT mn.content,
                       1 - (me.embedding <=> %s::vector) AS similarity
                FROM memory_embeddings me
                JOIN memory_nodes mn ON me.node_id = mn.id AND me.user_id = mn.user_id
                WHERE me.user_id = %s
                ORDER BY me.embedding <=> %s::vector
                LIMIT %s
            """, (str(query_embedding), user_id, str(query_embedding), limit))
            rows = cur.fetchall()

            return [
                (content, score)
                for content, score in rows
                if score >= threshold
            ]
    except Exception as e:
        log.warning(f"recall_by_embedding failed: {e}")
        return []