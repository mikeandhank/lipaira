# Lipaira Project Roadmap
## Two-Project Operatorure: Nexus Server + Lipaira Client
**Last Updated:** March 18, 2026

---

# ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                    NEXUS SERVER (Cloud)                        │
│                 api.nexusos.ai / nexus.ai                       │
├─────────────────────────────────────────────────────────────────┤
│  Purpose: Auth, LLM Routing, Billing, User Management          │
│                                                                     │
│  User signs up → gets Nexus API Key → configures LLM preference  │
│  Client calls API → Server routes to LLM → deducts credits     │
└─────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ X-Nexus-Key: sk-nexus-xxx
                                    │
┌─────────────────────────────────────────────────────────────────┐
│                    NEXUSOS CLIENT (Local)                       │
│                  Runs on User's Machine / VPS                  │
├─────────────────────────────────────────────────────────────────┤
│  Purpose: Agent Runtime, Memory, Tools, Local Processing      │
│                                                                     │
│  Agent Runtime, Memory System, Skills, Tool Engine, Inner Life  │
│  Communicates with Nexus Server for LLM access                 │
└─────────────────────────────────────────────────────────────────┘
```

---

# NEXUS SERVER

## What We Have (✅)
| Component | File | Status |
|-----------|------|--------|
| **Full Server (Flask)** | server_full.py | ✅ DONE |
| Multi-provider LLM routing | server_full.py | ✅ DONE |
| Cost/Quality Slider | server_full.py | ✅ DONE |
| Credit system | server_full.py | ✅ DONE |
| Usage tracking | server_full.py | ✅ DONE |
| Encryption at rest | encryption.py | ✅ DONE |
| JWT Auth with bcrypt | server_full.py | ✅ DONE |
| API Key system | server_full.py | ✅ DONE |
| Chat endpoint | server_full.py | ✅ DONE |
| **Swarm Orchestration** | swarm_orchestration.py | ✅ DONE |
| **Automation Templates** | automation_templates.py | ✅ DONE |
| **Twilio Integration** | twilio_integration.py | ✅ DONE |
| Landing Page | index.html | ✅ DONE |

## Completed This Week (March 18)
- ✅ Security audit fixes (bcrypt, atomic transactions, input validation)
- ✅ Swarm multi-agent orchestration API
- ✅ 6 automation templates (CRM sync, email parser, support triage, etc.)
- ✅ Twilio SMS/Voice integration
- ✅ Landing page with modern dark UI
- ✅ Legacy code archived

## What We Need (🔴)

### Phase 1: Production Ready
| # | Item | Status |
|---|------|--------|
| 1 | Deploy server_full.py to VPS | 🔴 NOT STARTED |
| 2 | Set up PostgreSQL on VPS | 🔴 NOT STARTED |
| 3 | Configure environment variables | 🔴 NOT STARTED |
| 4 | Test /api/chat with real API key | 🔴 NOT STARTED |

### Phase 2: Integrations
| # | Item | Status |
|---|------|--------|
| 5 | Twilio credentials (production) | 🔴 NOT STARTED |
| 6 | Stripe payment integration | 🔴 NOT STARTED |
| 7 | Custom domain (nexusos.ai) | 🔴 NOT STARTED |

### Phase 3: Scaling
| # | Item | Status |
|---|------|--------|
| 8 | Redis for sessions/cache | 🔴 NOT STARTED |
| 9 | Celery for background tasks | 🔴 NOT STARTED |
| 10 | Usage dashboard UI | 🔴 NOT STARTED |

---

# NEXUSOS CLIENT

## What We Have (✅)
| Component | File | Status |
|-----------|------|--------|
| Agent Runtime | agent_runtime.py | ✅ DONE |
| Multi-agent Pool | agent_pool.py | ✅ DONE |
| Memory System | memory_consolidation.py | ✅ DONE |
| Skills System | skills.py | ✅ DONE |
| Tool Engine | tool_engine.py | ✅ DONE |
| MCP Protocol | mcp_server.py | ✅ DONE |
| Inner Life | affect_layer.py, theory_of_mind.py, etc | ✅ DONE |
| Background Processing | background_processor.py | ✅ DONE |
| Process Manager | (in agent_runtime) | ✅ DONE |
| CLI Client | client_cli.py | ✅ DONE |

## What We Need (🔴)

### Phase 1: Server Communication
| # | Item | Status |
|---|------|--------|
| 1 | Connect CLI to server_full.py | 🔴 NOT STARTED |
| 2 | Nexus API Key config | 🔴 NOT STARTED |
| 3 | /chat command (call server) | 🔴 NOT STARTED |

### Phase 2: Integration
| # | Item | Status |
|---|------|--------|
| 4 | Offline mode (Ollama fallback) | 🔴 NOT STARTED |
| 5 | Usage sync | 🔴 NOT STARTED |

### Phase 3: Proprietary GUI 🔴 NEW
| # | Item | Status |
|---|------|--------|
| 6 | **Mac-inspired chat-first UI** | 🔴 PLANNED |
| 7 | Command bar (type to control everything) | 🔴 PLANNED |
| 8 | Cross-platform (Electron/Tauri) | 🔴 PLANNED |
| # | Item | Status |
|---|------|--------|
| 15 | iOS App (App Store) | 🔴 NOT STARTED |
| 16 | Android App (Play Store) | 🔴 NOT STARTED |
| 17 | Push notifications | 🔴 NOT STARTED |
| 18 | Mobile context harvesting | 🔴 NOT STARTED |

---

# NEXUSOS CLIENT

## What We Have (✅)
| Component | File | Status |
|-----------|------|--------|
| Agent Runtime | agent_runtime.py | ✅ DONE |
| Multi-agent Pool | agent_pool.py | ✅ DONE |
| Memory System | memory_consolidation.py | ✅ DONE |
| Skills System | skills.py | ✅ DONE |
| Tool Engine | tool_engine.py | ✅ DONE |
| MCP Protocol | mcp_server.py | ✅ DONE |
| Inner Life | affect_layer.py, theory_of_mind.py, etc | ✅ DONE |
| Background Processing | background_processor.py | ✅ DONE |
| Process Manager | (in agent_runtime) | ✅ DONE |

## What We Need (🔴)

### Phase 1: Server Communication
| # | Item | Status |
|---|------|--------|
| 1 | CLI client (connects to API) | ✅ DONE (client_cli.py) |
| 2 | Nexus API Key config | 🔴 NOT STARTED |
| 3 | /chat command (call server) | 🔴 NOT STARTED |
| 4 | /config command (sync settings) | 🔴 NOT STARTED |

### Phase 2: Integration
| # | Item | Status |
|---|------|--------|
| 5 | Offline mode (Ollama fallback) | 🔴 NOT STARTED |
| 6 | Usage sync | 🔴 NOT STARTED |
| 7 | Auto-retry on failure | 🔴 NOT STARTED |

### Phase 3: Proprietary GUI 🔴 NEW
| # | Item | Status |
|---|------|--------|
| 8 | **Mac-inspired chat-first UI** | 🔴 PLANNED |
| 9 | Command bar (type to control everything) | 🔴 PLANNED |
| 10 | "Type app name to open" - no clicking | 🔴 PLANNED |
| 11 | AI anticipates needs, suggests actions | 🔴 PLANNED |
| 12 | Cross-platform (Electron/Tauri) | 🔴 PLANNED |
| 13 | Local or remote server connection | 🔴 PLANNED |

---

# DATABASE TABLES

## Added This Session
```sql
-- Users (extended)
ALTER TABLE users ADD COLUMN nexus_api_key TEXT UNIQUE;
ALTER TABLE users ADD COLUMN credits numeric DEFAULT 0;
ALTER TABLE users ADD COLUMN subscription_tier TEXT DEFAULT 'free';

-- User LLM Config
CREATE TABLE user_llm_config (
    user_id TEXT REFERENCES users(id),
    provider TEXT DEFAULT 'openai',
    model TEXT DEFAULT 'gpt-4o-mini',
    fallback_provider TEXT,
    fallback_model TEXT,
    is_default BOOLEAN DEFAULT true
);

-- API Keys
CREATE TABLE api_keys (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id),
    key_prefix TEXT DEFAULT 'sk-nexus-',
    key_hash TEXT NOT NULL,
    name TEXT,
    last_used TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);
```

---

# API ENDPOINTS

## Implemented
| Endpoint | Method | Status |
|----------|--------|--------|
| /api/auth/register | POST | ✅ DONE |
| /api/auth/login | POST | ✅ DONE |
| /api/config | GET | ✅ DONE |
| /api/config | PUT | ✅ DONE |
| /api/models | GET | ✅ DONE |
| /api/chat | POST | ✅ DONE |
| /api/credits | GET | ✅ DONE |
| /api/credits/purchase | POST | ✅ DONE |
| /api/usage | GET | ✅ DONE |
| /api/usage/summary | GET | ✅ DONE |

---

# SECURITY MODEL

## Keys Hierarchy
1. **Nexus API Key** (`sk-nexus-xxx`) - identifies user, no LLM access
2. **Provider Keys** - encrypted on server (OpenAI, Anthropic, etc.)
3. **User BYOK Keys** - optional, user provides their own

## Security Rules
- [x] Provider keys encrypted at rest (pgcrypto)
- [ ] Keys decrypted only in RAM at request time
- [ ] Every key use logged
- [ ] Keys rotatable

---

# REVENUE MODEL

```
User buys credits → We route to LLM → We keep 5.5% fee
                                   
User BYOK → We route → We charge 5% of provider cost
```

---

# COST/QUALITY SLIDER

## Concept
User-facing control in webapp to balance cost vs. response quality:

```
┌─────────────────────────────────────────────────────────────┐
│  Cost/Quality Slider                                        │
│                                                             │
│  🦉 Cheap                          Expensive 🦅            │
│  [────●────────────]                                       │
│                                                             │
│  Model: gpt-4o-mini    →    Model: gpt-4o                 │
│  Cost: $0.15/1M        →    Cost: $2.50/1M                 │
│  Speed: Fast            →    Speed: Moderate                │
│  Use: Quick tasks     →    Use: Complex reasoning         │
└─────────────────────────────────────────────────────────────┘
```

## Implementation
| Setting | Model | Cost Level | Use Case |
|---------|-------|------------|----------|
| ⚡️ Speed | gpt-4o-mini | $0.15/1M | Quick queries, summaries |
| ⚖️ Balanced | claude-sonnet | $3.00/1M | General tasks |
| 💎 Quality | gpt-4o / opus | $2.50-15/1M | Complex reasoning |
| 🧠 Deep | o1-preview | $15/1M | Hard problems |

## Auto-Selection
Based on detected task complexity:
- Simple Q&A → cheapest model
- Code generation → mid-tier
- Complex reasoning → premium

---

# MOBILE APPS

## Purpose
- Control agents on-the-go
- Real-time notifications
- Harvest additional context (location, calendar, activity)

## iOS / Android Features

| Feature | Description |
|---------|-------------|
| **Agent Control** | Start/stop/pause agents |
| **Chat Interface** | Talk to agents directly |
| **Push Notifications** | Agent completions, alerts |
| **Context Feed** | Calendar, location, activity |
| **Usage Dashboard** | Credits, costs, history |
| **Settings** | Model preferences, alerts |

## Context Harvesting
```
┌────────────────────────────────────────────────────────┐
│  Mobile Context (optional, user-controlled)            │
├────────────────────────────────────────────────────────┤
│  📍 Location    - "Near coffee shop, suggest agent"  │
│  📅 Calendar   - "Meeting in 10min, summarize docs"   │
│  🔔 Activity   - "Missed call, draft response"       │
│  📸 Photos     - "Analyze this receipt"               │
│  🎤 Voice      - "Transcribe & summarize"             │
└────────────────────────────────────────────────────────┘
```

## Technical Stack
- **iOS**: Swift/SwiftUI + React Native
- **Android**: Kotlin + React Native
- **Backend**: Existing Nexus Server APIs

---

# IMMEDIATE NEXT STEPS

1. **Deploy server_api.py** to production
2. **Add real provider API keys** (OpenAI, Anthropic)
3. **Test end-to-end** (register → get key → chat)
4. **Deploy client** instructions
