# Projects - Durable Knowledge

## Lipaira (formerly Nexus AI)

### Pricing Model (2026-03-30)
- **Fee Structure:** 5.5% fee collected at credit **purchase** (POS), not per-call
- User buys $100 credits → pays $105.50 (fee immediately earned revenue)
- Credits deducted 1:1 against provider cost (no per-call margin tracking)
- Simpler accounting: fee = revenue, credits = cost

### Provider Costs (per 1M tokens)
| Model | Input | Output |
|-------|-------|--------|
| Claude Opus 4 | $15.00 | $75.00 |
| Claude Sonnet 3.5 | $3.00 | $15.00 |
| Claude Haiku 3 | $0.25 | $1.25 |
| GPT-4o | $2.50 | $10.00 |
| GPT-4o-mini | $0.15 | $0.60 |
| Gemini 1.5 Pro | $1.25 | $5.00 |
| Gemini 1.5 Flash | $0.075 | $0.30 |

### OpenRouter Integration (2026-03-30)
- All models (claude-*, gpt-*, gemini-*) now route through OpenRouter
- Pricing: 1.30x markup on OpenRouter rates
- Ollama remains direct for local inference

### Skills System (2026-04-02)
- **Framework Built:** `/skills/` directory with base.py, registry.py
- **Security Model:** Skills fetch OAuth tokens from DB via get_integration_tokens() - never accept tokens from workflow definitions
- **Core Skills:** Email (send, draft with templates), QuickBooks (invoices via sandbox API), Google Calendar (events), Memory (recall, store)
- **Working Skills:** Email sending via Resend (noreply@lipaira.ai)
- **OAuth Status:** Notion working, QuickBooks sandbox ready, Google OAuth ready, Microsoft removed (msal not installed)

### Skills Count (2026-04-03)
- 21 skills in framework
- **Critical Fix (2026-04-03):** OpenRouter tool calling - preserve `tool_calls` and `tool_call_id` fields in message serialization (previously stripped, causing calendar skill failures)

### Billing System (2026-03-31)
- **Signup Bonus:** $50 credits
- **Per-Chat Cost:** $0.01 (1 cent deducted per chat call)
- **Balance Metrics:** balance_usd, runway_days, daily_burn_usd
- **Database Tables:** credit_transactions, agent_subscriptions, auto_refill_settings, llm_usage.cost
- **Known Issue:** Chat endpoint returns 500 (LLM/agent code issue, not billing)

### UI/UX Updates (2026-04-02)
- Login page now accessible
- OAuth Connect buttons wired for: google, quickbooks, notion, slack, square, hubspot, pipedrive, salesforce, zoho
- Sidebar added to Dashboard
- Integration list API endpoint fixed (/api/integrations/list)
- Header fix: X-Nexus-Key → X-Lipaira-Key

### Database (2026-04-02)
- Added business_id column to users
- Added QB token columns (quickbooks_access_token, etc.)
- Added workflow table (for future)

### Infrastructure
- EC2: 3.147.192.198
- API: https://api.lipaira.ai
- Frontend: https://lipaira.ai
- Network: lipaira-net (Docker)

### Deployment
- **ALWAYS use CI/CD:** commit → push → GitHub Actions deploys
- **NEVER use:** docker cp, docker exec edits, manual scp
- Manual docker cp creates uncommitted local changes → breaks CI/CD git pull
- If stuck: `git stash` → `git pull` → rebuild

---

### SPEC v5 Development (2026-04-04)
- Expanded spec from ~2,000 to ~3,900 lines
- **6 bugs fixed from Claude review:**
  - Provisioner missing network.connect, wait loop, schema
  - Cross-domain SQL → Python reasoning
  - Health check ollama removed
  - WorkerPool async/sync (wrapped with asyncio.to_thread)
  - Deploy docker run → docker-compose
  - Block 1 incomplete markers added
- **Block 1 Verification (all passing):**
  - pgvector v0.8.2 installed
  - memory_embeddings table exists (58 embeddings)
  - graph.conn bug fixed (standing facts returns 12 items)
  - Health check passes
  - Auth working
- **Gap Identified:** Chat API endpoint, semantic recall, token refresh, freemium tier need implementation

### UI/UX Updates (2026-04-04)
- New `/integrations` page with connect/disconnect functionality
- Brand SVG logos for each integration with brand-colored backgrounds
- Toast notifications on OAuth success/failure
- Connect button in sidebar under "Manage"

---

## Domain Curriculum
- 13 domains planned, 8 completed