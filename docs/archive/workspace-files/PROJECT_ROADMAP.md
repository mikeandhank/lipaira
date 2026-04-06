# Nexus Project Operatorure
## Two-Project Model: Nexus Server + Lipaira Client

**Last Updated:** March 17, 2026

---

# ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           NEXUS SERVER (Cloud)                         │
│                        api.nexusos.ai / nexus.ai                        │
├─────────────────────────────────────────────────────────────────────────┤
│  Purpose: Authentication, LLM Routing, Billing, User Management       │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │ Auth         │  │ LLM Router   │  │ Billing      │                │
│  │ - Nexus API  │  │ - OpenAI     │  │ - Credits    │                │
│  │   Key        │  │ - Anthropic  │  │ - Usage      │                │
│  │ - JWT        │  │ - Google     │  │ - Invoices   │                │
│  │ - Web Panel  │  │ - Pooled     │  │              │                │
│  └──────────────┘  └──────────────┘  └──────────────┘                │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │ User Config  │  │ Webhooks     │  │ Analytics    │                │
│  │ - Model      │  │ - Events     │  │ - Usage      │                │
│  │ - Provider   │  │ - Alerts     │  │ - Revenue    │                │
│  │ - Fallback   │  │              │  │              │                │
│  └──────────────┘  └──────────────┘  └──────────────┘                │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ API Calls
                                    │ (Nexus API Key)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         NEXUSOS CLIENT (Local)                          │
│                     Runs on User's Machine / VPS                       │
├─────────────────────────────────────────────────────────────────────────┤
│  Purpose: Agent Runtime, Memory, Tools, Local Processing              │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │ Agent        │  │ Memory       │  │ Process      │                │
│  │ Runtime      │  │ System       │  │ Manager      │                │
│  │ - Define     │  │ - Semantic   │  │ - Background │                │
│  │ - Execute    │  │ - Episodic   │  │ - Stdin/out  │                │
│  │ - Pool       │  │ - Working    │  │ - Pause      │                │
│  └──────────────┘  └──────────────┘  └──────────────┘                │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │ Skills       │  │ Tool Engine  │  │ Inner Life   │                │
│  │ - File       │  │ - MCP        │  │ - Affect     │                │
│  │ - HTTP       │  │ - Custom     │  │ - Socratic   │                │
│  │ - Process    │  │ - Registry   │  │ - Pattern    │                │
│  └──────────────┘  └──────────────┘  └──────────────┘                │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Communication Layer (calls Nexus Server)                       │  │
│  │ - POST /chat (send message, receive response)                  │  │
│  │ - GET  /config (get user's LLM preferences)                    │  │
│  │ - POST /usage (sync usage stats)                               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

# NEXUS SERVER (Cloud)

## Current Assets (What We Have)
| File | Status | Purpose |
|------|--------|---------|
| api_server_v5.py | ✅ DONE | Main API server |
| llm_integration.py | ✅ DONE | Multi-provider LLM routing |
| billing.py | ✅ DONE | Credit system, usage tracking |
| auth.py | ✅ DONE | JWT authentication |
| database.py | ✅ DONE | PostgreSQL operations |
| encryption.py | ✅ DONE | pgcrypto encryption |
| agent_*.py | ✅ DONE | Agent management |
| webhooks.py | ✅ DONE | Webhook system |

## Server Roadmap

### Phase 1: Core Infrastructure

| # | Item | Status | Priority |
|---|------|--------|----------|
| 1 | Nexus API Key system | 🔴 NOT STARTED | CRITICAL |
| 2 | User LLM config storage | 🔴 NOT STARTED | CRITICAL |
| 3 | Server-side LLM routing | 🔴 NOT STARTED | CRITICAL |
| 4 | Connect billing to routing | 🔴 NOT STARTED | CRITICAL |
| 5 | Basic /chat endpoint | 🔴 NOT STARTED | CRITICAL |

### Phase 2: Authentication & Users

| # | Item | Status | Priority |
|---|------|--------|----------|
| 6 | Register/Login endpoints | 🔴 NOT STARTED | HIGH |
| 7 | API key generation (sk-nexus-xxx) | 🔴 NOT STARTED | HIGH |
| 8 | API key validation middleware | 🔴 NOT STARTED | HIGH |
| 9 | User dashboard API | 🔴 NOT STARTED | MEDIUM |

### Phase 3: Billing & Payments

| # | Item | Status | Priority |
|---|------|--------|----------|
| 10 | Credit purchase flow | 🔴 NOT STARTED | HIGH |
| 11 | Stripe integration | 🔴 NOT STARTED | HIGH |
| 12 | Usage API (per-user) | 🔴 NOT STARTED | MEDIUM |
| 13 | Invoice generation | 🔴 NOT STARTED | MEDIUM |

### Phase 4: Advanced Features

| # | Item | Status | Priority |
|---|------|--------|----------|
| 14 | Model fallback chain | 🔴 NOT STARTED | MEDIUM |
| 15 | Load balancing across providers | 🔴 NOT STARTED | LOW |
| 16 | Real-time usage WebSocket | 🔴 NOT STARTED | LOW |
| 17 | Admin panel | 🔴 NOT STARTED | MEDIUM |

---

# NEXUSOS CLIENT (Local)

## Current Assets (What We Have)
| File | Status | Purpose |
|------|--------|---------|
| agent_runtime.py | ✅ DONE | Agent execution engine |
| agent_pool.py | ✅ DONE | Multi-agent management |
| agent_routes.py | ✅ DONE | Agent CRUD |
| background_processor.py | ✅ DONE | Background tasks |
| affect_layer.py | ✅ DONE | Emotional processing |
| pattern_library.py | ✅ DONE | Cognitive patterns |
| inner_narrative.py | ✅ DONE | Self-reflection |
| theory_of_mind.py | ✅ DONE | User modeling |
| socratic_dialogue.py | ✅ DONE | Learning dialogue |
| memory_consolidation.py | ✅ DONE | Memory management |
| tool_engine.py | ✅ DONE | Tool execution |
| mcp_server.py | ✅ DONE | MCP protocol |
| skills.py | ✅ DONE | Skill system |

## Client Roadmap

### Phase 1: Core Runtime

| # | Item | Status | Priority |
|---|------|--------|----------|
| 1 | Local agent definition (YAML/JSON) | 🔴 NOT STARTED | CRITICAL |
| 2 | Message queue (server communication) | 🔴 NOT STARTED | CRITICAL |
| 3 | /chat command (send to server) | 🔴 NOT STARTED | CRITICAL |
| 4 | /config command (sync settings) | 🔴 NOT STARTED | HIGH |
| 5 | Basic CLI interface | 🔴 NOT STARTED | HIGH |

### Phase 2: Server Integration

| # | Item | Status | Priority |
|---|------|--------|----------|
| 6 | Nexus API Key config | 🔴 NOT STARTED | CRITICAL |
| 7 | Automatic retry on failure | 🔴 NOT STARTED | HIGH |
| 8 | Offline mode (Ollama fallback) | 🔴 NOT STARTED | MEDIUM |
| 9 | Usage sync | 🔴 NOT STARTED | MEDIUM |

### Phase 3: Advanced Client Features

| # | Item | Status | Priority |
|---|------|--------|----------|
| 10 | Local memory (when offline) | 🔴 NOT STARTED | MEDIUM |
| 11 | Web UI (local) | 🔴 NOT STARTED | LOW |
| 12 | Desktop app wrapper | 🔴 NOT STARTED | LOW |

---

# DATABASE SCHEMA

## Users Table (Extended)
```sql
users:
  - id (UUID)
  - email
  - password_hash
  - name
  - nexus_api_key (sk-nexus-xxx) -- our key, not provider
  - credits (numeric)
  - subscription_tier (free/pro/enterprise)
  - created_at
  - tenant_id
```

## User LLM Config
```sql
user_llm_config:
  - user_id (FK)
  - provider (openai/anthropic/google/...)
  - model (gpt-4o/claude-sonnet/...)
  - fallback_provider
  - fallback_model
  - is_default (boolean)
```

## Credit System
```sql
credit_purchases:
  - id
  - user_id
  - amount_paid
  - credits_added
  - our_fee
  - provider (stripe)
  - status
  - created_at

llm_usage:
  - id
  - user_id
  - provider
  - model
  - input_tokens
  - output_tokens
  - provider_cost
  - credits_deducted
  - created_at
```

## Provider Keys (Encrypted)
```sql
provider_keys:
  - id
  - provider
  - encrypted_key
  - label
  - is_default

user_provider_keys:
  - id
  - user_id
  - provider
  - encrypted_key
  - label
```

---

# API ENDPOINTS

## Nexus Server API

### Authentication
```
POST   /api/auth/register     - Create account
POST   /api/auth/login        - Get JWT + API key
POST   /api/auth/refresh     - Refresh token
GET    /api/auth/me           - Get current user
```

### API Key
```
GET    /api/keys              - List user's API keys
POST   /api/keys              - Create API key
DELETE /api/keys/:id          - Revoke API key
```

### LLM Configuration
```
GET    /api/config            - Get user's LLM config
PUT    /api/config            - Update LLM preferences
GET    /api/models            - List available models
```

### Chat (Main Endpoint)
```
POST   /api/chat              - Send message, get response
       Headers: X-Nexus-Key: sk-nexus-xxx
       Body: { message: "...", model: "optional" }
```

### Billing
```
GET    /api/credits           - Get credit balance
POST   /api/credits/purchase  - Buy credits
GET    /api/usage             - Get usage history
GET    /api/usage/summary     - Get usage summary
```

---

# SECURITY MODEL

## Key Hierarchy
```
1. NEXUS API KEY (sk-nexus-xxx)
   └── Identifies user
   └── No LLM provider access
   └── Used for all client-server communication

2. PROVIDER KEYS (encrypted on server)
   └── OpenAI, Anthropic, Google, etc.
   └── Encrypted at rest (pgcrypto)
   └── Decrypted only at request time, in memory
   └── Never logged, never exported

3. USER BYOK KEYS (encrypted on server)
   └── User provides their own provider keys
   └── Same security as provider keys
   └── 5% fee on usage
```

## Security Rules
- [ ] Nexus API Key never stored in logs
- [ ] Provider keys decrypted only in RAM
- [ ] Every key use logged for audit
- [ ] Keys rotatable (regenerate)
- [ ] BYOK mode optional

---

# REVENUE MODEL

## OpenRouter-Style
```
User buys credits from us
   │
   ▼
We route their requests to LLM providers
   │
   ▼
We keep 5.5% fee (minimum $0.80 per purchase)
   │
   ▼
User can also BYOK (bring their own keys)
   │
   ▼
We charge 5% of their provider costs
```

## Pricing Tiers
```
FREE TIER:
- 1000 free credits on signup
- Limited to certain models
- For testing/evaluation

PRO TIER ($9.99/month):
- $10/month credit allowance
- All models available
- Priority routing
- Usage dashboard

ENTERPRISE:
- Custom credit packages
- Dedicated infrastructure
- SSO/SAML
- SLA guarantee
```

---

# IMPLEMENTATION PRIORITY

## Immediate (This Week)

### Server
1. [ ] Create Nexus API Key generation
2. [ ] Add nexus_api_key to users table
3. [ ] Create /api/chat endpoint that routes to LLM
4. [ ] Connect usage tracking to /chat

### Client
1. [ ] Create simple CLI that calls /api/chat
2. [ ] Add Nexus API Key config
3. [ ] Basic message loop

## Short-Term (This Month)

### Server
1. [ ] User registration/login
2. [ ] Stripe integration for credits
3. [ ] Usage dashboard API
4. [ ] Model fallback logic

### Client
1. [ ] Offline mode with Ollama
2. [ ] Configuration sync
3. [ ] Web UI

---

# NOTES

- Server runs on our infrastructure (Hostinger)
- Client runs anywhere (user's VPS, laptop, etc.)
- Communication via REST API
- We never give users provider keys - we route for them
- BYOK is optional for users who want full control
