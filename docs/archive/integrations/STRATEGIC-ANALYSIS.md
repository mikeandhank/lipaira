# Lipaira Integrations — Strategic Analysis

**Date:** March 31, 2026  
**Purpose:** Document strategic observations before building DNS/website integrations

---

# What This Reveals About Our Product

## 1. We're Building a Hub, Not a Tool

**Current model:** Lipaira is an AI agent you chat with.

**This integration model:** Lipaira becomes the **central nervous system** connecting a business's digital tools.

The shift:

| Tool Mindset | Hub Mindset |
|--------------|-------------|
| You use Lipaira *instead of* doing work | You tell Lipaira once, it propagates *everywhere* |
| Single point of interaction | Single source of truth |
| Chat interface is primary | Chat is one interface, APIs are others |

## 2. The Operator Pattern is Required

We cannot have GoDaddy adapter, Squarespace adapter, Shopify adapter floating independently. The user needs **one** interface (Operator) that:

- Understands intent ("they want to update pricing")
- Routes to correct adapter(s) (GoDaddy + Squarespace + Shopify)
- Synthesizes results ("Updated pricing on all 3 platforms")
- Handles errors gracefully ("2 of 3 updated, Shopify needs reconnection")

**Currently we don't have this architecture.**

## 3. We're Becoming Infrastructure

This is both powerful and risky:

**Good:**
- Inescapable value — switching means updating 5+ places manually
- High switching costs
- Deepens product-market fit for service businesses

**Concerning:**
- If Lipaira goes down, their business operations stop
- Need robust error handling
- Need graceful degradation
- Need clear "I'm having trouble" messages

---

# Problems Outside This Spec

## 1. The Operator Operatorure (Not Built)

The "Operator" that dispatches to specialist agents doesn't exist yet.

**What's missing:**
- Intent classification ("user wants to update pricing")
- Adapter routing ("send to GoDaddy + Squarespace + Shopify")
- Response synthesis ("Updated pricing on all 3 platforms")
- Multi-turn context ("we were talking about pricing...")

## 2. Conversation State Management

**Current state:** Each message is stateless.

**We need to track:**
- What task are we working on?
- What platforms are connected?
- What did we already do in this conversation?
- What clarifying questions need answering?

## 3. Connection Management UI

**No UI for:**
- "Connect GoDaddy" flow with API key input
- "View my connected services"
- "Disconnect / Reconnect"
- "Test connection"

## 4. Credential Expiry Handling

**What happens when:**
- GoDaddy API key is revoked?
- Shopify token is invalidated?
- User changes GoDaddy password?

**Current behavior:** Silent failure.

**We need:**
- Proactive checking (daily? weekly?)
- User notification ("Your GoDaddy connection needs attention")
- Clear reconnection flow

## 5. Multi-Platform Transaction Safety

If user says "update pricing" and we update GoDaddy, then Squarespace fails:

- Do we rollback GoDaddy?
- Do we tell user "2 of 3 updated, Squarespace failed"?
- Do we retry automatically?
- Do we queue for later?

**No spec for this.**

## 6. Webhook Infrastructure

Shopify can push webhooks (new order, etc.). We have no webhook handling:

- Need endpoint to receive webhooks
- Need to verify webhook signatures (HMAC)
- Need to handle events we don't support yet
- Need to queue/process asynchronously

---

# What's Missing / Broken

## Missing:

1. **Operator orchestrator** — The brain that routes requests
2. **Intent parser** — Understanding "update my pricing" vs "add a subdomain"
3. **Connection UI** — Visual integration management
4. **Credential expiry detection** — Proactive re-auth prompts
5. **Task queue** — For async/long-running operations
6. **Webhook receiver** — For server-side events from Shopify

## Broken / Fragile:

1. **Single-task assumption** — What if user manages multiple businesses? (Not addressed)
2. **No rollback** — Failed updates leave inconsistent state
3. **Hardcoded provider list** — Adding new providers requires code changes
4. **No sandbox** — Testing integrations requires real credentials
5. **No connection health scoring** — Just "connected" or "disconnected"

---

# What Could Be Better

## 1. Unified Task System

Instead of hardcoding "update pricing" in every adapter:

```
Task: UPDATE_PRICING
├── platforms: [godaddy, squarespace, shopify]
├── parameters: [{name: "item", required: true}, {name: "price", required: true}]
├── execute: (platform, params) => platform.update_price(params)
├── validate: (params) => is_valid_price(params.price)
└── rollback: (platform, original) => platform.restore_price(original)
```

## 2. Plugin Operatorure for Adapters

Instead of hardcoding adapters, make them auto-discoverable:

```python
# adapters/godaddy.py
@register_adapter("godaddy", "registrar")
class GoDaddyAdapter: ...

# Auto-discovers all adapters
adapters = discover_adapters()
```

## 3. Connection Health Scoring

Not just "connected" or "disconnected":

| Status | Meaning | Action |
|--------|---------|--------|
| `green` | Working, tokens valid | None |
| `yellow` | Working, tokens expire soon | Notify user |
| `red` | Needs reconnection | Prompt to reconnect |
| `gray` | Never connected | Show in available |

## 4. Preview Mode

Before making changes, show "preview" of what would happen:

```
I'll update:
- GoDaddy: Service Call $150 → $175
- Squarespace: Service Call $150 → $175  
- Shopify: Service Call $150 → $175

[Preview] [Cancel] [Confirm All]
```

---

# Recommendations

## Build Priority

| Priority | Build This First | Why |
|----------|------------------|-----|
| **1** | GoDaddy DNS only | Simplest API, highest value for target customer |
| **2** | Connection UI | Validates credential flow, tangible for users |
| **3** | Operator + Task system | Enables multi-platform dispatch without hardcoding |
| **4** | Credential expiry handling | Prevents silent failures |
| **5** | Preview mode | Builds trust before making changes |

## Strategic Question

**Should we build GoDaddy DNS only first** (simplest path to revenue), **or build the Operator architecture first** (foundation for everything)?

---

# Product Vision Alignment

## "Lipaira = Your Entire Office in Your Pocket"

This integration system is the physical manifestation of that vision:

| Office Function | Lipaira Integration |
|-----------------|---------------------|
| Phone receptionist | AI chat + voice |
| Bookkeeper | QuickBooks integration |
| Marketing | Website + email |
| IT | Domain + DNS + SSL |
| Sales | Shopify orders |

We're building the IT layer.

---

# Open Questions

1. How does this fit with the Operator architecture?
2. What happens when credentials expire?
3. How do we handle partial failures in multi-platform updates?
4. What's the pricing model for integrations?
5. Should we support multiple businesses per user?
6. How do we handle users who manage other people's businesses (agencies)?

---

# Related Documents

- `SPEC-DNS-WEBSITE-INTEGRATIONS.md` — Technical spec
- `SPEC-OPERATOR-ARCHITECTURE.md` — Future work
- `SPEC-CONNECTION-UI.md` — Future work