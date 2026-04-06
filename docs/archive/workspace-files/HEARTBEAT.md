# HEARTBEAT.md

# Proactive Checks (rotate through these)

## Every Check-In (2-4x daily):
- **Email scan** — Any urgent messages? Flag anything relevant to Nexus AI, revenue, or opportunities
- **Opportunity scan** — Any relevant news in AI agents, SMB automation, or our target markets?
- **Task progress** — Any background tasks completed? Report results

## 1x Daily (pick one):
- **Competitor watch** — Quick scan of Nexus AI competitor developments
- **Market research** — Deep dive on one segment of our target market
- **Content ideas** — Note 2-3 content angles that could drive waitlist signups

## Weekly:
- **Strategy review** — Summarize what we learned, any pivots to consider

---

# Hank's Operating Rules

**Rule: Try first, ask later.** If Hank can fix a problem himself, he always tries first before asking the user to do it.

---

# What I'm Working On

**Current autonomous project:** Lipaira - True Agent OS (Apple-quality)

**Progress (2026-03-16):**
- ✅ All prior items...
- ✅ **True OS Capabilities** (Mar 16 evening):
  - Process Manager - real stdin/stdout, background execution, pause/resume
  - IPC System - agent-to-agent messaging, pub/sub, request/response
  - Workflow Engine - multi-step workflows, conditions, approvals
  - SSO Login UI - modern dark theme with Okta/Azure/Google buttons
  - Usage Dashboard - user-first stats (tokens, costs, trends)
- ✅ **Tier 1 Complete** - DB Migrations, Syscall Filter, Trigger Chains, SIEM Export
- ✅ **Tier 2 Complete** - OAuth2/SSO, Custom RBAC, SAML/SCIM
- ✅ **Tier 3 Complete** - Auth docs, API flow docs

- ✅ **SECURITY AUDIT RECEIVED (Mar 16 evening)**
  - Grade: C+ (needs hardening)
  - CRITICAL issues found: exposed server IP, JWT HS256, no password complexity
  - HIGH issues: no CSRF, open registration, no real payments

- ✅ **SECURITY FIXES DEPLOYED:**
  - 1. Disable root SSH ✅
  - 2. JWT RS256 (asymmetric) ✅
  - 3. Password complexity (12+ chars, breach check) ✅
  - 4. UUID migration helpers ✅
  - 5. CSRF protection ✅
  - 6. CAPTCHA + rate limiting ✅
  - 7. Stripe payment integration ✅
  - Removed TEST_CREDENTIALS.md (exposed server IP)

- ✅ **Roadmap: 24/66 complete (expanded for audit)**
- ✅ Server healthy: PostgreSQL ✅ Redis ✅ Ollama ✅

**What's next:**
- ~~Input sanitization (SQL injection, XSS)~~ ✅ DONE (Mar 17)
- ~~Database encryption at rest~~ ✅ DONE
- ~~Streaming/WebSocket for chat~~ ✅ DONE
- ~~Landing Page~~ ✅ DONE (Mar 18)

---

**TODAY'S PROGRESS (2026-03-19):**

**✅ LIPAIRA COMPLIANCE INFRASTRUCTURE (14 files):**
- Logging: schema.py, openrouter.py
- Database: transactions.py, stripe_webhook.py
- Accounting: revenue_cogs.py, reconciliation.py
- Legal: gdpr_inventory.py, tos_version_control.py, dsr_workflow.py, compliance_ops.py
- Infrastructure: iam_policies.py, s3_hash_verification.py, cloudwatch_alerts.py

**✅ PRICING MODEL IMPLEMENTED (2026-03-19):**
- Credits: Customer gets $X for $X payment
- Fee: 5.5% added on top (non-refundable)
- Refund: Unused credits only (no fee returned)
- Credits NEVER expire

**✅ SECURITY HARDENING ON LIVE SERVER:**
- Fixed 0.0.0.0 binding → 127.0.0.1 (in Python code)
- UFW firewall enabled - blocks DB/Redis/API from outside
- Input sanitization already deployed ✅

**✅ DOCS CREATED:**
- SECURITY_REQUIREMENTS.md
- docs/API.md

**✅ AWS Server:** 3.147.192.198 (via AWS ALB)

**✅ ALB + Cloudflare Setup:**
- AWS ALB: lipaira-dns-lb-1013914831.us-east-2.elb.amazonaws.com
- Cloudflare proxying lipaira.ai and api.lipaira.ai
- GTM (Google Tag Manager) installed
- Security group: 8080 only from ALB

**✅ AWS Secrets Manager Keys:**
- lipaira/anthropic-api-key ✅
- lipaira_OpenAI_API_Key (IAM permission needed)
- lipaira_Google_API_Key (IAM permission needed)
- lipaira_OpenAI_API_Key (needs IAM permission)
- lipaira_Google_API_Key (needs IAM permission)

---

## Today's Progress (2026-03-25)

**✅ FULL END-TO-END PRODUCT LIVE:**
- AWS Secrets Manager integration (API keys loaded securely)
- Anthropic API key loaded from AWS Secrets Manager ✅
- Full chat flow working: Sign up → Chat → Credits deducted ✅
- Credit deduction atomic in Postgres ✅
- 5.5% fee calculation working ✅
- llm_usage table created ✅
- Docker network isolation verified (lipaira-net)

**✅ LIPAIRA.AI LIVE:**
- Domain: https://lipaira.ai ✅
- Traefik installed and configured ✅
- Let's Encrypt SSL auto-issued ✅
- React frontend serving ✅
- API at /api and /health ✅

**✅ SECURITY:**
- GitHub repo set to private
- New PAT rotated
- Pre-commit security hook installed
- .env in .gitignore

**✅ UI Round 2:**
- Landing page (/)
- Markdown rendering in chat
- Typing indicator
- Message bubbles styled
- Credits with 2 decimal places

---

## Today's Progress (2026-03-28)

**✅ OAUTH PROVIDERS (Google, Microsoft, QuickBooks):**
- All 3 OAuth flows working (302 redirects)
- Secrets loaded from AWS Secrets Manager (30 secrets)
- Credentials: lipaira/Google_OAuth_Client_ID, lipaira/MICROSOFT_CLIENT_ID, lipaira/QuickBooks_Client_ID

**✅ MEMORY SYSTEM PHASE 1:**
- Extracted CumulativeMemoryGraph as standalone module (memory_graph.py)
- No legacy/workspace dependencies
- recall_semantic() wired before LLM call
- add_memory() wired async after LLM response
- Verified: agent remembers context across API calls

**✅ ONBOARDING:**
- POST /api/onboarding sets user name
- One field: {name: "Michael"} → enters chat

**✅ NAMING RENAME (nexus → lipaira):**
- require_nexus_key → require_auth
- sk-nexus- → lp- (backward compatible)
- nexus-server → lipaira in health endpoints

**🔄 NEXT:**
- Phase 2 memory sweeps (QB, Google context extraction)
- Profile page showing memories

---

## Today's Progress (2026-03-30)

**✅ GMAIL OAUTH INTEGRATION:**
- Google OAuth backend already built (google_oauth.py)
- Registered routes in server_full.py
- Fixed container env vars (DB, Redis, Google credentials)
- Added "Connect Gmail" button to Dashboard UI
- OAuth flow working: lipaira.ai/api/auth/google/connect → 302 to Google

**✅ SERVER FIX:**
- Fixed syntax error in server_full.py (was causing crash)
- Reverted to working oauth image with proper env vars
- Server healthy: curl localhost:8080/health → {"status":"ok"}

**Scopes enabled:**
- gmail.send, gmail.readonly
- calendar.events, calendar.readonly
- drive.file
- contacts.readonly

---

## Today's Progress (2026-04-01)

**✅ PRICING UPDATE:**
- Operator base fee → $1.00/day ($30/month)

**✅ DATABASE MIGRATIONS:**
- businesses table created (18 users migrated)
- business_id columns added to: user_integrations, agent_subscriptions, memory_nodes, conversation_messages
- integration_health table created
- workflows table created

**✅ WORKFLOW SYSTEM (COMPLETE):**
- Dynamic workflow engine - AI generates custom workflows from goals
- LLM integration wired for workflow generation
- Workflow storage in DB (save, list, delete, toggle, run)
- Workflows added to agent memory
- Optimized cron scheduler (caches workflows, inline execution)

**✅ INVOICE CHASE WORKER:**
- Queries QuickBooks for overdue invoices
- Generates HTML chase emails (friendly → urgent → final)
- Sends via Resend

**✅ WEBHOOK RECEIVER:**
- Shopify, Squarespace, GoDaddy webhook endpoints
- Signature verification
- Async processing

**✅ CONNECTION MANAGEMENT UI:**
- IntegrationCard component with health status
- Connect/test/disconnect flows
- API endpoints: /api/integrations/list, /test, /disconnect

**✅ SERVER FIX:**
- Symlink for lipaira_client module
- Fixed duplicate endpoint error
- API healthy: https://api.lipaira.ai/health → {"status":"ok"}

---

**What's left (MVP):**
- End-to-end test invoice chase
- Demo flow
- First paying user

---

## Today's Progress (2026-04-05)

**✅ BLOCK 2 COMPLETE (from prior session):**
- Item 1: Per-user Postgres provisioner
- Item 2: Freemium model (tier routing, tools disabled for free)
- Item 3: Twilio SMS approval flow
- Item 4: Invoice chase workflow
- Item 5: Morning briefing engine
- Item 6: Activity log API

**✅ BLOCK 3 IN PROGRESS:**
- Item 7: Microsoft Outlook OAuth wired ✅
- Item 8: Web search/fetch skills registered ✅

**⚠️ Needs:**
- BRAVE_SEARCH_API_KEY in Secrets Manager
- Continue Block 3 Item 9+