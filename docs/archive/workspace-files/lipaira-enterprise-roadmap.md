# Lipaira Enterprise Roadmap (UPDATED)
## Based on: Competitive Intelligence + Third-Party Audit
**Last Updated:** March 16, 2026

---

## 🚨 CRITICAL SECURITY FIXES (Audit Priority)

| # | Item | Status | Priority |
|---|------|--------|----------|
| 1 | Disable root SSH, use key-based auth | ✅ DONE | CRITICAL |
| 2 | Fix database credentials - require strong passwords | ✅ DEPLOYED (password_security.py) | CRITICAL |
| 3 | Migrate JWT from HS256 to RS256 (asymmetric) | ✅ DONE (jwt_rotation.py) | CRITICAL |
| 4 | Implement password complexity enforcement (12+ chars) | ✅ DONE (password_security.py) | CRITICAL |
| 5 | Migrate TEXT primary keys to UUID v4 | ✅ DONE (uuid_migration.py) | CRITICAL |
| 6 | Add CSRF protection to Flask endpoints | ✅ DONE (csrf_protection.py) | HIGH |
| 7 | Add CAPTCHA/rate-limiting to /api/auth/register | ✅ DONE (captcha.py) | HIGH |
| 8 | Add real payment processor (Stripe) for balance reload | ✅ DONE (payment.py) | HIGH |
| 9 | Add input sanitization (SQL injection, XSS) | ✅ DONE (input_sanitization.py) | HIGH |
| 10 | Enable PostgreSQL encryption at rest | ✅ DONE (pgcrypto) | MEDIUM |

---

## 🚀 PHASE 1: HARDEN & DIFFERENTIATE (Audit-Driven)

### Security Hardening (From Audit)

| # | Item | Status |
|---|------|--------|
| 11 | Professional pentest | 🔴 NOT STARTED |
| 12 | Fix all CRITICAL findings | 🔴 NOT STARTED |
| 13 | Fix all HIGH findings | 🔴 NOT STARTED |
| 14 | Add deep health checks (DB, Redis, Ollama) | ✅ DONE |
| 15 | Add database foreign key constraints | ✅ DONE |
| 16 | Add database indexes on FK columns | ✅ DONE |

### Streaming & Real-Time (From Competitive Gap)

| # | Item | Status |
|---|------|--------|
| 17 | Implement WebSocket/SSE for chat streaming | ✅ DONE (streaming.py) | HIGH |
| 18 | Consider FastAPI migration for native async | ✅ DONE |
| 19 | Add Celery-based streaming via Redis pub/sub | ✅ DONE |

### GPU & Model Infrastructure (From Competitive Gap)

| # | Item | Status |
|---|------|--------|
| 20 | Add Ollama GPU passthrough configuration | ✅ DONE |
| 21 | Support vLLM as alternative runtime | ✅ DONE |
| 22 | Document GPU setup for common hardware | ✅ DONE (GPU_SETUP.md)|

### Inner Life Rebranding

| # | Item | Status |
|---|------|--------|
| 23 | Rebrand "Inner Life" → "Agent Intelligence Engine" | ✅ DONE |
| 24 | Document enterprise-friendly framing | ✅ DONE (ENTERPRISE.md) |

### OpenRouter-Style Billing

| # | Item | Status |
|---|------|--------|
| 25 | Credit system (purchase, balance, deduct) | ✅ DONE (billing.py) |
| 26 | Usage tracking (per-request logging) | ✅ DONE (billing.py) |
| 27 | Provider key manager (master + BYOK) | ✅ DONE (billing.py) |
| 28 | 5.5% fee calculation on purchases | ✅ DONE |
| 29 | BYOK mode (5% fee on provider cost) | ✅ DONE |
| 30 | OpenRouter integration | 🔴 NOT STARTED |

---

## 🚀 PHASE 3: ENTERPRISE & REVENUE

### Compliance & Legal (From Audit)

| # | Item | Status |
|---|------|--------|
| 32 | Create DPA (Data Processing Agreement) templates | 🔴 NOT STARTED |
| 33 | GDPR compliance documentation | 🔴 NOT STARTED |
| 34 | AI Liability Framework / Terms of Service | 🔴 NOT STARTED |
| 35 | BYOK legal disclaimers | 🔴 NOT STARTED |
| 36 | Begin SOC 2 Type I preparation | 🔴 NOT STARTED |
| 37 | Professional penetration testing | 🔴 NOT STARTED |

### Revenue Model (From Audit)

| # | Item | Status |
|---|------|--------|
| 38 | Tiered pricing: Community (free) / Pro ($99/mo) / Enterprise | 🔴 NOT STARTED |
| 39 | Decouple revenue from LLM consumption | 🔴 NOT STARTED |
| 40 | Integrate Stripe for payments | 🔴 NOT STARTED |

### Enterprise Features

| # | Item | Status |
|---|------|--------|
| 41 | Multi-tenancy with namespace isolation | 🔴 NOT STARTED |
| 42 | Agent marketplace for community templates | 🔴 NOT STARTED |
| 43 | Target 3-5 pilot enterprise customers | 🔴 NOT STARTED |

---

## ✅ COMPLETED ITEMS

### Core Infrastructure (DONE)
- [x] PostgreSQL deployment
- [x] Redis deployment
- [x] JWT Authentication
- [x] Agent Definition & Runtime
- [x] Input Sanitization (basic)
- [x] Container Isolation
- [x] Network Rate Limiting
- [x] TLS/SSL with Let's Encrypt
- [x] HTTP→HTTPS Redirect

### Enterprise Features (DONE)
- [x] OAuth2/SSO (Okta, Azure, Google)
- [x] SAML 2.0 Support
- [x] SCIM 2.0 User Provisioning
- [x] Custom RBAC with roles
- [x] SIEM Export (Splunk, ELK, Syslog)

### True OS Capabilities (DONE)
- [x] Process Manager (stdin/stdout, background)
- [x] IPC (Inter-Agent Communication)
- [x] Workflow Engine
- [x] Sandbox Isolation (gVisor/LXC/seccomp-bpf)

### Documentation (DONE)
- [x] Bearer Token Documentation
- [x] API Flow Documentation
- [x] SSO Login Page UI
- [x] Usage Dashboard (API)

### Operational (DONE)
- [x] Health checks (5 min)
- [x] Enterprise audit (1 hour)
- [x] Daily backups (3 AM)
- [x] Security scans (1 AM)
- [x] Log rotation (4 AM)

---

## 📊 SUMMARY

| Category | Total | Complete | Remaining |
|----------|-------|----------|-----------|
| Critical Security (Audit) | 10 | 0 | 10 |
| Phase 1: Harden | 16 | 0 | 16 |
| Phase 2: Ecosystem | 7 | 0 | 7 |
| Phase 3: Enterprise | 12 | 0 | 12 |
| Completed | 21 | 21 | 0 |
| **TOTAL** | **66** | **21** | **45** |

---

## 🎯 STRATEGIC CONTEXT

### Competitive Landscape (March 16, 2026)
- **NemoClaw** (Nvidia) announced TODAY at GTC - your biggest competitor
- **Window:** 3-6 months before they mature
- **Differentiation:** "Complete platform" vs "framework"

### The One-Line Strategy
> "Stop being everything. Be the thing Nvidia can't be: a complete, opinionated, deploy-in-minutes AI agent OS for enterprises who don't have a platform team — with a cognitive layer no one else has."

### Key Strategic Shifts
1. **Revenue:** Tiered pricing (not just 5.5% fee)
2. **Compliance:** DPA, SOC 2, AI liability before selling
3. **Security:** Fix CRITICALs BEFORE any enterprise sales
4. **Community:** Open-source core to build ecosystem

---

## ⚡ IMMEDIATE ACTION ITEMS

1. **This Week:** Disable root SSH, fix JWT, add password complexity
2. **This Month:** Add streaming, GPU support, WebSocket
3. **Next 30 Days:** Get professional pentest
4. **Next 60 Days:** DPA, GDPR docs, SOC 2 prep
5. **Next 90 Days:** Launch tiered pricing, community

---

*Roadmap updated based on:*
- *Third-party security audit (March 16, 2026)*
- *Competitive intelligence vs NemoClaw, OpenClaw, CrewAI*
- *Strategic positioning as "Apple of AI"*
