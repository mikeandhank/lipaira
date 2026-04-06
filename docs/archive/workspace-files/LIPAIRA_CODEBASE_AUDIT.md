# Lipaira Codebase Audit

**Generated:** 2026-04-04  
**Scope:** /data/.openclaw/workspace  

---

## STEP 1: File Tree Summary

### Active Python Files (Non-Legacy)

| Directory | Count | Notes |
|-----------|-------|-------|
| `.` (root) | 18 | Core server, billing, etc |
| `skills/` | 31 | Skill implementations |
| `integrations/` | 6 | Integration handlers |
| `lipaira-client/` | 23 | Client-side code |
| `lipaira-providers/` | 9 | Model providers |
| `operator_layer/` | 5 | Operator logic |
| `nexusos/` | 24 | Legacy API servers |
| `lipaira-compliance/` | 14 | Compliance components |

**Total: ~130 active Python files**

### Duplicate/Redundant Directories

| Directory | Status |
|-----------|--------|
| `nexusos/` | Legacy v1-v3 API servers (deprecated) |
| `legacy/v2/nexusos-v2/` | Full v2 implementation (superseded) |
| `lipaira-web/` | Old frontend (replaced by /lipaira-web) |

---

## STEP 2: Unused Functions

**Analysis:** 1,562 defined, 1,501 called, 713 potentially unused

### Top Unused Functions

| Function | File | Likely Status |
|----------|------|---------------|
| `accept_tos` | lipaira-compliance/legal/tos_version_control.py | May be needed |
| `activate_automation` | nexusos/automation_templates.py | Legacy |
| `add_security_headers` | nexusos/server_full.py | Could be used |
| `asana_callback` | server_full.py | Route exists but may not be wired |
| `asana_connect` | server_full.py | Route exists but may not be wired |
| `asana_disconnect` | server_full.py | Route exists but may not be wired |
| `api_chat` | nexusos/api_server_v3.py | Old endpoint |
| `broadcast_event` | nexusos/event_bus.py | May be needed |
| `calculate_price` | lipaira-providers/providers.py | May be used elsewhere |
| `cancel_subscription` | nexusos/billing.py | Route exists |

**Recommendation:** Many of these are route handlers that may not be registered in the main app.

---

## STEP 3: Routes Analysis

### Registered Routes (Active)

From `server_full.py`:
- `/api/auth/register` - POST
- `/api/auth/login` - POST
- `/api/config` - GET, PUT
- `/api/models` - GET
- `/api/credits` - GET
- `/api/credits/purchase` - POST
- `/health` - GET

From `billing.py`:
- `/api/billing/calculate` - POST
- `/api/billing/subscribe` - POST
- `/api/billing/webhook` - POST
- `/api/billing/status` - GET
- `/api/billing/usage` - GET
- `/api/billing/cap` - PUT

From `twilio_integration.py`:
- `/api/twilio/config` - GET
- `/api/twilio/sms/send` - POST
- `/api/twilio/sms` - GET
- `/api/twilio/sms/webhook` - POST
- `/api/twilio/call/initiate` - POST
- `/api/twilio/call` - GET

From `swarm_orchestration.py`:
- `/api/swarm/create` - POST
- `/api/swarm/<swarm_id>/execute` - POST
- `/api/swarm` - GET

### Routes Not Connected (Files Exist But Not Imported)

- `lipaira-providers/user_settings.py` - `/api/agents/<agent_id>/execute`
- `lipaira-compliance/legal/dsr_workflow.py` - `/api/dsr`, `/api/dsr/{request_id}`
- `integrations/routes.py` - Likely not imported in main server

---

## STEP 4: Skills Registry vs Files

### Registered Skills (25 total)

| Skill | Integration Required |
|-------|---------------------|
| email_send | - |
| email_draft | - |
| quickbooks_get_invoices | quickbooks |
| quickbooks_get_customers | quickbooks |
| calendar_get_events | - |
| google_business_update | google_business |
| google_ads_get_campaigns | google |
| gmail_read | google |
| gmail_send | google |
| memory_recall | - |
| memory_store | - |
| notion_search | notion |
| notion_create_page | notion |
| zoom_get_meetings | zoom |
| zoom_create_meeting | zoom |
| calendly_get_scheduled_events | calendly |
| calendly_get_event_types | calendly |
| meta_get_ad_performance | meta_ads |
| meta_get_campaigns | meta_ads |
| canva_get_designs | canva |
| canva_create_design | canva |
| trello_get_cards | trello |
| trello_create_card | trello |
| asana_get_tasks | asana |
| asana_create_task | asana |

### Skill Files That Exist But Aren't Registered

| File | Reason |
|------|--------|
| `skills/youtube_transcript/youtube_transcript.py` | YouTube skill not registered |
| `skills/orchestration/swarm.py` | Swarm skill not in registry |
| `lipaira-client/skills/` directory | Entire directory not imported |

---

## STEP 5: Dead Code / Orphaned Files

### Files Not Imported Anywhere

```
lipaira-client/test_calendar_skill.py
lipaira-cloud/ (entire directory)
memory/knowledge/ (research files, not code)
nexusos-android/
nexusos-ios/
nexusos-gui/
nexusos-memory/
nexusos-webapp/
nexus-ai-landing/
outreach/
easy-install/
docs/ (markdown, not code)
scripts/ (deployment scripts)
migrations/ (SQL only)
```

### Duplicate API Servers

| File | Status |
|------|--------|
| `server_full.py` | **ACTIVE** - main production server |
| `nexusos/server_full.py` | Duplicate - should delete |
| `nexusos/api_server.py` | Legacy v1 |
| `nexusos/api_server_v2.py` | Legacy v2 |
| `nexusos/api_server_v3.py` | Legacy v3 |
| `legacy/v2/nexusos-v2/api_server_v4.py` | Never used |
| `legacy/v2/nexusos-v2/api_server_v5.py` | Never used |

---

## STEP 6: Docker & Infrastructure

### docker-compose.yml Services

```yaml
services:
  lipaira-api:   # ACTIVE
  lipaira-web:   # ACTIVE
  postgres:      # ACTIVE
  redis:         # ACTIVE
  traefik:       # ACTIVE
```

### What Exists But Not in Compose

- No separate Ollama container (removed from infrastructure)
- No legacy services

### Dockerfiles

| File | Used By |
|------|---------|
| `Dockerfile` | lipaira-api |

---

## STEP 7: Environment Variables

### Required ENV Vars (Referenced in Code)

| Variable | Used In | Status |
|----------|---------|--------|
| DATABASE_URL | All DB operations | ✅ Set |
| REDIS_HOST | Caching | ✅ Set |
| ANTHROPIC_API_KEY | LLM calls | ✅ Set |
| OPENAI_API_KEY | Embeddings | ✅ Set |
| OPENROUTER_API_KEY | Model routing | ✅ Set |
| GOOGLE_CLIENT_ID | OAuth | ✅ Set |
| GOOGLE_CLIENT_SECRET | OAuth | ✅ Set |
| MICROSOFT_CLIENT_ID | OAuth | Needs set |
| MICROSOFT_CLIENT_SECRET | OAuth | Needs set |
| QUICKBOOKS_CLIENT_ID | OAuth | Needs set |
| QUICKBOOKS_CLIENT_SECRET | OAuth | Needs set |
| STRIPE_SECRET_KEY | Billing | Needs set |
| RESEND_API_KEY | Email | Needs set |
| TWILIO_ACCOUNT_SID | SMS | Needs set |
| TWILIO_AUTH_TOKEN | SMS | Needs set |

### Missing From .env (Referenced But Not Set)

```
BRAVE_SEARCH_API_KEY
COHERE_API_KEY
DASHSCOPE_API_KEY
DEEPSEEK_API_KEY
MISTRAL_API_KEY
NVIDIA_API_KEY
NOTION_API_KEY
PERPLEXITY_API_KEY
AZURE_OPENAI_API_KEY
AZURE_OPENAI_ENDPOINT
DISCORD_WEBHOOK_URL
GITHUB_TOKEN
GOOGLE_ADS_DEVELOPER_TOKEN
```

---

## SUMMARY: What Can Be Deleted

### High Priority (Safe to Delete)

1. **Duplicate API Servers:**
   - `nexusos/api_server.py`
   - `nexusos/api_server_v2.py`
   - `nexusos/api_server_v3.py`
   - `nexusos/server_full.py` (keep root version)
   - `legacy/v2/nexusos-v2/api_server_v4.py`
   - `legacy/v2/nexusos-v2/api_server_v5.py`

2. **Entire Unused Directories:**
   - `nexusos-android/`
   - `nexusos-ios/`
   - `nexusos-gui/`
   - `nexusos-memory/`
   - `nexusos-webapp/`
   - `nexus-ai-landing/`
   - `outreach/`
   - `easy-install/`
   - `<data/`
   - `