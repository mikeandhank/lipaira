# Agent Briefing

## Session April 3, 2026

### Tool Calling Fix (April 3, 2026)

**Root cause:** OpenRouterAdapter.build_request() stripped tool_calls and tool_call_id from all messages:
```python
msgs.extend([{'role': msg['role'], 'content': msg['content']}...])
```

**Fix:** Preserve tool fields when building message list. Now passes proper OpenRouter format:
- Assistant: `{"role": "assistant", "content": null, "tool_calls": [...]}`
- Tool result: `{"role": "tool", "tool_call_id": "...", "content": "..."}`

Tool format is OpenAI-compatible (OpenRouter standard). Works for all models: MiniMax, Claude, GPT-4o, etc. `tools` parameter must be included in BOTH LLM calls. `tool_choice: "auto"` should be set on requests with tools.

### Verified Working (April 3, 2026)
- Calendar returns real Google events in formatted table
- Tool-use loop: LLM calls skill → result fed back → LLM presents to user
- Cross-conversation memory recall
- Token auto-refresh for expired OAuth tokens
- Conversation persistence

### Fixed
- operator_context.py: DB connection was singleton (closed after first use). Fixed to create fresh connection per function call.
- operator_context.py: _get_integrations() used wrong column (connected=true → status='connected'). Google/Notion now visible.
- server_full.py: conversation_messages INSERT was missing entirely. Added after LLM response. Messages now persist across sessions.
- operator_soul.py: Added NEVER rules for memory usage and third-party references.
- CI/CD: Removed npm build step (dist/ committed to repo, npm not on EC2). Deploy works cleanly again.
- lipaira-gateway/: Deleted. Was dead code, never in docker-compose. All routing through server_full.py.
- Chat UI: Enter sends, Shift+Enter newlines.

### Working
- Cross-conversation memory recall (verified)
- Google + Notion integrations visible to Operator
- Calendar skill implemented (returns events)
- Conversation persistence to DB

## Technical Debt

### Memory recall threshold (priority: medium)
Current threshold: 0.1 (lowered from 0.4)
Problem: keyword matching scores too low even for
 relevant memories. At 0.1, irrelevant memories
 will start appearing as memory_nodes grows.
Fix needed: Switch _get_relevant_memories() to use
 vector embeddings instead of keyword matching.
 memory_embeddings table already exists in schema.
 CumulativeMemoryGraph.recall_semantic() uses vectors
 if embeddings are populated.
 The extraction step should generate and store
 embeddings when saving to memory_nodes.
Timeline: Before first 10 paying users.

### Google OAuth granular split (done April 3, 2026)
Replaced monolithic 'google' provider with:
gmail, google_calendar, google_drive, google_business, google_ads
Each has separate scopes, separate token rows, separate sweeps.
If adding new Google services: follow this pattern.
Do NOT create a monolithic 'google' integration again.

### Integration sync frequency
Current: Daily at 6am UTC (via background sweep)
Consider: Webhook-based updates for QB (invoice paid events),
Gmail (new message events), Calendar (event created/changed)
Real-time would be better than polling for high-value events.

### Still Needed
- memory_nodes extraction: Conversations save to conversation_messages but semantic memory_nodes not populated. The memory_store skill exists but isn't called after each exchange.
- Calendar results not surfacing in chat responses — Operator runs the skill but doesn't present results correctly. Tool-use response handling needs investigation.
- Ollama container running for 8+ days — consuming RAM. Verify nothing uses it, then stop and remove.

---

## What Does NOT Exist (and why)
- **lipaira-gateway/** — deleted April 2026. Was dead code,
 never wired into docker-compose. All auth, billing,
 and chat routing lives in server_full.py directly.
 Do not recreate a separate gateway service.
- **ollama container** — stopped April 3, 2026. Ollama image
 kept on disk for future enterprise/air-gapped use. Not in
 docker-compose — will not restart on deploy. To re-enable:
 add ollama service back to docker-compose.yml and configure
 as a model option in providers.py.

## CI/CD Pipeline — WORKING (March 29, 2026)
GitHub Actions deploys automatically on every push to main.
Deploy time: ~53 seconds.

Workflow: .github/workflows/deploy.yml
Key steps:
1. git pull origin main
2. docker build -t lipaira-api:latest .
3. docker stop/rm lipaira-api
4. docker-compose up -d --no-deps lipaira-api
5. docker restart traefik
6. Wait for api-catchall router to register (up to 35s)
7. curl -f http://localhost/health

CRITICAL: Traefik needs restart after each deploy to 
pick up new container labels. The deploy waits for 
api-catchall@docker to appear in Traefik's router list 
before running the health check.

Monitor: github.com/mikeandhank/nexus-ai/actions

## API Endpoints

### Onboarding (Added March 28, 2026)
- `GET /api/onboarding/status` → `{completed: true/false}`
- `POST /api/onboarding/complete` → saves name to user_profiles + memory
- Frontend: Onboarding.jsx — one field, redirects to /chat
- Auth: accepts both X-Lipaira-Key and Authorization: Bearer
- New users redirected to /onboarding on first load
## Conversation Persistence (Added March 28, 2026)
- conversation_messages table: user_id, role, content, model, created_at
- GET /api/conversation/history → last 50 messages oldest first
- POST /api/chat saves both turns in background thread
- Chat.jsx loads history on mount, optimistic updates on send
- Auto-scroll to bottom on new messages
