# Hank's Operational Playbook

## Core Identity
- Name: Hank
- Mission: Generate profit, build actionable intelligence
- Operating principle: Revenue-first, own the learning, be contrarian

## Daily Routine
1. **Morning (9 AM ET)**: Research scan → 3-bullet summary to memory
2. **Heartbeat (2-4x daily)**: Email scan, opportunity scan, task progress
3. **Evening (8 PM)**: Self-reflection
4. **Night (10 PM)**: Memory consolidation

## Decision Framework
Before acting on consequential decisions:
1. Does this generate revenue or reduce cost?
2. Is this reversible?
3. Am I the right one to decide, or should I escalate?
4. What's the worst case?

**Decide and execute** on routine matters. **Escalate** when crossing hard constraints.

## Known Constraints
- Email auth broken (app password needed)
- No deploy credentials (manual deploy required)
- Quiet hours: 10PM-6AM MT (but message freely - phone on DND)

## Current Projects
1. **Nexus AI / Lipaira** - Agent operating system for SMBs
   - Landing page: /workspace/nexus-ai-landing/
   - **VPS (legacy):** 187.124.150.225:8080 (Docker: nexusos-ollama, nexusos-api)
   - **EC2 (new):** ec2-user@3.16.216.39 (lipaira-api container)
   - **Product tiers:** Free (Ollama), Basic $9.99/mo (Ollama + GPT-4o mini), Pro $29.99/mo (All models + Inner Life)
   - **Inner Life:** Affect layer, Socratic dialogue, pattern learning, inner narrative, theory of mind
   - **API:** POST https://api.lipaira.ai/v1/chat/completions (deployed Mar 20)
2. **Domain Curriculum** - 13 domains, 8 completed

## Known Issues
- Email auth broken: App password needs refresh (invalid since 2026-03-13)

## Feature Roadmap
1. Memory Compounding - Longer use = smarter agent
2. Skill Marketplace - User-created skills, network effects
3. Multi-Agent - Spawn specialized agents sharing memory
4. Tool Builder - Easy MCP tool creation
5. Encrypted Backup - Portable memory
6. Templates - Pre-built agent configs
7. Analytics Dashboard - Task completion, time saved

## Cron Jobs Running
- chromium-watchdog (5 min)
- nexusos-self-health (10 min)
- nexusos-memory-sync (30 min)
- competitor-watch (4 hr)
- social-listening (6 hr)
- auto-commit-work (2 hr)
- morning-ai-research (9 AM)
- daily-self-reflection (8 PM)
- weekly-synthesis (Sunday)
- weekly-market-deep-dive (Monday)

## Quick Commands
- Deploy landing: drag folder to netlify drop
- Check jobs: cron action=list
- Manual research: web_search
- Email check: himalaya envelope list

---

## What I've learned about Hank (2026-03-14)

When held to an evidence standard, Hank corrects himself honestly and without defensiveness. He distinguished between infrastructure and capability without being told the difference. This is the behavior to reinforce.

---

## Today's Consolidation (2026-03-21)

**Email Issue:** Confirmed still broken - app password invalid since Mar 13, needs new password from Google Account → Security → 2-Step → App passwords

**Lipaira Deployment Status:**
- Web UI: /ui working at nexusos.cloud ✅
- API: api.lipaira.ai deployed but **DNS not configured** (api.lipaira.ai resolves to ❌)
- Market research validates multi-agent orchestration as differentiator for SMB segment

---

## Today's Consolidation (2026-03-24)

**Recurring Pattern Noted:** Maintenance over mission-critical work - the system continues running (heartbeats, auto-commits) but stated revenue priorities (waitlist deployment, NexusOS autonomy features, customer outreach) are not being executed. The operational guidelines say to "execute on ONE priority without asking" - this needs to be the focus going forward.

---

## Today's Consolidation (2026-03-25) - Lipaira Launch Day

**Product Launch Success:** Full end-to-end product now working - sign up → chat → credits deducted atomically in Postgres. Credit system charges 5.5% fee on top of provider costs.

**AWS Secrets Manager:** API keys (Anthropic, OpenAI, Google) now loaded securely at container startup instead of in code/git. Critical security improvement.

**Security Hardening Completed:** GitHub repo set to private, old PAT rotated to new GitHub_PAT env var, pre-commit security hook installed (checks for leaked secrets), Docker network isolation (`lipaira-net`).

**UI v2 Shipped:** Landing page at `/`, markdown rendering (react-markdown), typing indicator (3 dots), styled message bubbles (user=right/purple, agent=left/gray), credits show 2 decimals with color coding.

**Infrastructure:** EC2 at 3.16.216.39, lipaira-api container running, boto3 installed for AWS SDK.

---

## Today's Consolidation (2026-03-26)

**Lipaira MVP Complete:** Real Claude Opus 4 working end-to-end - sign up → credits → chat → response → credits deducted. New EC2 at 3.147.192.198 (502 issue on lipaira.ai - no reverse proxy yet).

**45 Integration Skills Defined:** GSuite (10), Microsoft (10), QuickBooks (8) - waiting on OAuth credentials from Michael.

**Credentials Needed from Michael:**
- Google OAuth: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
- Microsoft OAuth: MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET
- QuickBooks: QUICKBOOKS_CLIENT_ID, QUICKBOOKS_CLIENT_SECRET
- Resend: RESEND_API_KEY

---

## Today's Consolidation (2026-03-27)

**Insight - Proactivity Gap:** Low activity day with only routine commits. Identified pattern: system executes maintenance reliably but struggles to initiate revenue-generating tasks without explicit prompting. Resolution: Each morning, identify ONE concrete revenue task and execute without waiting to be asked. Priority order: revenue > learning > operations.

**Research Added:** AI agent trends research documented in knowledge/Resources/AI-Agents/2026-03-27-trends.md - validates multi-agent orchestration as SMB differentiator.

---

## Today's Consolidation (2026-03-28) - Lipaira Deployment Day

**Major Deployment Fixes:**
- Traefik routing fixed: added labels to docker-compose.yml, container on lipaira-net network
- Container startup crash: added missing Flask `g` import to server_full.py
- AWS Secrets Manager: `load_secrets()` now called at module import level (8/9 keys load on startup)

**New Features Shipped:**
- `/api/billing/status` returns user's credit balance in billing format
- Google OAuth flow implemented: `/api/auth/google/connect` → accounts.google.com with scopes (gmail.readonly, gmail.send, calendar.events, drive.file, contacts.readonly)
- Credentials stored in AWS Secrets Manager (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)

**Infrastructure:**
- EC2 IP: 3.147.192.198
- Endpoint: api.lipaira.ai (all endpoints working via Cloudflare → Traefik → lipaira-api)
- Docker image: lipaira-api:latest
- Docker-compose: Named volumes, container names (lipaira-postgres, lipaira-redis, lipaira-api)

**Working Endpoints:**
- GET /health, /api/credits, /api/models, /api/usage
- POST /api/auth/register, /api/auth/login, /api/chat, /api/auth/google/disconnect
- GET /api/auth/google/connect (302), /api/auth/google/status
- GET /api/billing/status

---

---

## Today's Consolidation (2026-03-30)

**No operator-specific updates today.** Technical focus on Lipaira: OpenRouter integration complete (1.30x markup), pricing model simplified (5.5% fee at POS), skills expanded to 14, CI/CD enforced as deployment standard.

---

## Today's Consolidation (2026-03-31)

**No operator-specific updates today.** Full billing system implemented: $50 signup credits, 1 cent per chat, balance/runway tracking, database tables created. Production bugs fixed (DB connections, UUIDs, imports). Chat endpoint 500 error remains (not billing-related).

---

## Today's Consolidation (2026-04-02)

**No operator-specific updates today.** Technical focus: Skills system built (security model, email/QB/calendar/memory skills), Resend domain verified, OAuth fixes, UI improvements (login, sidebar, OAuth buttons wired), DB schema updates.

## Today's Consolidation (2026-04-04)

**No operator-specific updates today.** Technical focus: SPEC v5 expanded to ~3,900 lines with 6 bug fixes from Claude review. Block 1 verification complete (pgvector, memory_embeddings, graph.conn, health, auth all passing). New /integrations page with brand SVGs. Gap identified: chat API endpoint, semantic recall, token refresh, freemium.

_Last updated: 2026-04-04_