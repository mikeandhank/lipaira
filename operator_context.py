"""
OPERATOR_CONTEXT - Layer 2 of Lipaira's prompt architecture

Dynamic context per user/business/conversation.
Memory is retrieved in four passes before assembling the prompt.
"""

from datetime import datetime
import logging
import json
import os

def _get_db():
    """Get a fresh database connection. Caller must close it."""
    import psycopg2
    return psycopg2.connect(os.environ.get('DATABASE_URL'))

log = logging.getLogger(__name__)


def build_operator_context(user_id: str, business_id: str = None, first_message: str = "") -> str:
    """
    Build the dynamic context layer.
    Memory is retrieved in four passes before building any other context.
    Called once per conversation at the first message.
    """
    # Import here to avoid circular imports
    from server_full import get_memory_graph
    
    # ── Memory first ─────────────────────────────────────────────────────
    standing_facts = _get_standing_facts(user_id)
    relevant_memories = _get_relevant_memories(user_id, first_message)
    pending_items = _get_pending_items(user_id, business_id)
    recent_episodes = _get_recent_episodes(user_id)
    
    # ── Business profile ─────────────────────────────────────────────────
    business = _get_business(user_id)
    integrations = _get_integrations(user_id, business_id)
    
    # ── Skills ───────────────────────────────────────────────────────────
    skills = _get_available_skills()
    
    # ── Assemble context ─────────────────────────────────────────────────
    now = datetime.now()
    hour = now.hour
    tod = ("morning" if hour < 12 else "afternoon" if hour < 17 else "evening")
    
    name = business.get("business_name", "this business")
    owner = business.get("owner_name", "the owner")
    first = owner.split()[0] if owner else "there"
    tone = business.get("greeting_style", "professional")
    
    # Build memory section
    memory_section = _format_memory_section(
        standing_facts=standing_facts,
        relevant_memories=relevant_memories,
        pending_items=pending_items,
        recent_episodes=recent_episodes
    )
    
    return f"""
## BUSINESS

Name: {name}
Owner: {owner} (address as {first})
Type: {business.get('business_type', 'not specified')}
Location: {business.get('location', 'not specified')}
Services: {business.get('services', 'not specified')}
Pricing: {business.get('pricing', 'not specified')}
Hours: {business.get('working_hours', 'not specified')}
Team: {business.get('team', 'not specified')}

## COMMUNICATION STYLE

Tone: {tone}. Address the owner as {first}.

## MEMORY

{memory_section}

## AVAILABLE SKILLS (you can call these directly)

{skills}

## CONNECTED PLATFORMS

{', '.join(integrations) if integrations else 'None yet.'}

## NOW

{now.strftime('%A, %B %d, %Y')} — {tod}
""".strip()


def _get_available_skills() -> str:
    """Get list of available skills."""
    try:
        from skills.registry import skill_registry
        all_skills = skill_registry.list()
        
        skill_list = []
        for s in all_skills:
            skill_list.append(f"- {s['name']}: {s['description']}")
        
        return "\n".join(skill_list) if skill_list else "No skills available"
    except Exception as e:
        return f"Skills unavailable: {str(e)[:50]}"


def _format_memory_section(standing_facts: list, relevant_memories: list, 
                           pending_items: list, recent_episodes: list) -> str:
    """Assemble all memory layers into a structured prompt section."""
    parts = []
    
    if standing_facts:
        facts_str = '\n'.join(f' - {f}' for f in standing_facts)
        parts.append(f"STANDING FACTS (always true, high confidence):\n{facts_str}")
    
    if relevant_memories:
        rel_str = '\n'.join(f' - {m}' for m in relevant_memories)
        parts.append(f"RELEVANT TO THIS CONVERSATION:\n{rel_str}")
    
    if pending_items:
        pend_str = '\n'.join(f' - {p}' for p in pending_items)
        parts.append(f"PENDING — NEEDS ATTENTION:\n{pend_str}")
    
    if recent_episodes:
        ep_str = '\n'.join(f' - {e}' for e in recent_episodes)
        parts.append(f"RECENT CONTEXT (last conversations):\n{ep_str}")
    
    if not parts:
        return ("No memory yet for this user. "
                "Learn as much as possible from this conversation "
                "and store key facts using memory_store.")
    
    return '\n\n'.join(parts)


def _get_standing_facts(user_id: str) -> list:
    """
    Retrieve high-importance, high-confidence facts.
    Always injected regardless of the user's message.
    """
    conn = None
    try:
        conn = _get_db()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT content
                FROM memory_nodes
                WHERE user_id = %s
                AND node_type IN ('fact', 'preference',
                'procedural', 'identity')
                AND confidence >= 0.8
                ORDER BY confidence DESC, access_count DESC
                LIMIT 12
            """, (user_id,))
            rows = cur.fetchall()
            return [row[0] for row in rows if row[0]]
    except Exception as e:
        log.warning(f"[_get_standing_facts] {e}")
        return []
    finally:
        if conn:
            conn.close()


def _get_relevant_memories(user_id: str, query: str) -> list:
    """
    Semantic recall using vector embeddings.
    Falls back to keyword matching if embeddings unavailable.
    """
    if not query:
        return []

    conn = None
    try:
        conn = _get_db()

        # Try vector search first
        try:
            from memory_embeddings import recall_by_embedding
            results = recall_by_embedding(
                query=query,
                user_id=user_id,
                conn=conn,
                limit=8,
                threshold=0.65
            )
            if results:
                return [
                    f"{content} (relevance: {score:.0%})"
                    for content, score in results
                ]
        except Exception as e:
            log.warning(f"Vector search failed, using keyword: {e}")

        # Keyword fallback
        query_words = set(query.lower().split())
        with conn.cursor() as cur:
            cur.execute("""
                SELECT content FROM memory_nodes
                WHERE user_id = %s
                ORDER BY importance DESC, created_at DESC
                LIMIT 50
            """, (user_id,))
            all_nodes = cur.fetchall()

        scored = []
        for (content,) in all_nodes:
            if not content:
                continue
            content_words = set(content.lower().split())
            overlap = len(query_words & content_words)
            if overlap > 0:
                scored.append((content, overlap))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [content for content, _ in scored[:8]]

    except Exception as e:
        log.warning(f"[_get_relevant_memories] {e}")
        return []
    finally:
        if conn:
            conn.close()


def _get_pending_items(user_id: str, business_id: str = None) -> list:
    """Retrieve actionable pending items."""
    items = []
    conn = None
    try:
        conn = _get_db()
        cur = conn.cursor()
        
        # Invoice chases awaiting approval
        cur.execute("""
            SELECT COUNT(*), SUM(amount) FROM invoices
            WHERE user_id = %s AND status = 'pending'
        """, (user_id,))
        row = cur.fetchone()
        if row and row[0]:
            total = f"${float(row[1] or 0):,.2f}" if row[1] else ""
            items.append(f"{row[0]} invoice(s) awaiting approval" + (f" ({total} outstanding)" if total else ""))
        
    except Exception as e:
        log.warning(f"[operator_context._get_pending_items] {e}")
    finally:
        if conn:
            conn.close()
    
    return items


def _get_recent_episodes(user_id: str, limit: int = 3) -> list:
    """Retrieve summaries of recent conversation episodes."""
    conn = None
    try:
        conn = _get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT summary FROM conversation_episodes
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (user_id, limit))
        rows = cur.fetchall()
        
        episodes = []
        for row in rows:
            if row[0]:
                content = row[0]
                if isinstance(content, (bytes, memoryview)):
                    try:
                        content = bytes(content).decode('utf-8')
                    except Exception:
                        continue
                episodes.append(content[:200])
        return episodes
    except Exception as e:
        log.warning(f"[operator_context._get_recent_episodes] {e}")
        return []
    finally:
        if conn:
            conn.close()


def _get_business(user_id: str) -> dict:
    """Get business profile for user."""
    conn = None
    try:
        conn = _get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT display_name, context FROM user_profiles 
            WHERE user_id = %s
        """, (user_id,))
        row = cur.fetchone()
        
        if row:
            ctx = row[1] or {}
            return {
                "business_name": ctx.get("business_name") or "this business",
                "owner_name": ctx.get("owner_name") or row[0] or "the owner",
                "business_type": ctx.get("business_type") or "not specified",
                "location": ctx.get("location") or "not specified",
                "services": ctx.get("services") or "not specified",
                "pricing": ctx.get("pricing") or "not specified",
                "working_hours": ctx.get("working_hours") or "not specified",
                "team": ctx.get("team") or "not specified"
            }
    except Exception as e:
        log.warning(f"[operator_context._get_business] {e}")
    finally:
        if conn:
            conn.close()
    return {}


def _get_integrations(user_id: str, business_id: str = None) -> list:
    """Get connected integrations for user."""
    conn = None
    try:
        conn = _get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT provider FROM user_integrations
            WHERE user_id = %s AND status = 'connected'
        """, (user_id,))
        rows = cur.fetchall()
        return [r[0] for r in rows]
    except Exception as e:
        log.warning(f"[operator_context._get_integrations] {e}")
        return []
    finally:
        if conn:
            conn.close()


def build_system_prompt(user_id: str, business_id: str = None, first_message: str = "") -> str:
    """
    Build the full system prompt by combining Layer 1 (SOUL) + Layer 2 (CONTEXT).
    Layer 3 (TASK) is injected per operation.
    """
    from operator_soul import OPERATOR_SOUL
    context = build_operator_context(user_id, business_id, first_message)
    return f"{OPERATOR_SOUL}\n\n---\n\n{context}"