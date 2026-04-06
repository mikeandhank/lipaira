# Lipaira Model Registry

## Overview

Lipaira integrates with **OpenRouter** to provide access to 300+ AI models. We route requests based on user's quality preference, charge credits, and take a 5.5% fee.

---

## Pricing Model

| Component | Cost |
|-----------|------|
| **Provider Cost** | What OpenRouter charges (per 1M tokens) |
| **Our Fee** | 5.5% of provider cost |
| **User Pays** | Provider cost + 5.5% fee = credits deducted |

**Example:** GPT-4o Mini
- Provider: $0.15/1M input, $0.60/1M output
- Our fee (5.5%): $0.00825 + $0.033 = $0.04125 per 1M
- User charged: ~$0.16/1M tokens

---

## Quality Tiers

### ⚡ Speed (Fast & Cheap)
Best for: Simple queries, high volume, fast responses

| Model | Context | Best For |
|-------|---------|----------|
| `qwen/qwen3-coder-480b:free` | 32K | Code, speed |
| `google/gemini-2.0-flash-exp:free` | 1M | Long context, free |
| `meta-llama/llama-3.1-8b-instruct` | 128K | Fast, cheap |

### ⚖️ Balanced (Default)
Best for: Most tasks, good speed/quality

| Model | Context | Best For |
|-------|---------|----------|
| `openai/gpt-4o-mini` | 128K | Cheap, capable |
| `anthropic/claude-3-haiku` | 200K | Fast, smart |
| `mistralai/mistral-7b-instruct` | 32K | Open source |

### 🎯 Quality
Best for: Complex reasoning, writing, analysis

| Model | Context | Best For |
|-------|---------|----------|
| `openai/gpt-4o` | 128K | General purpose |
| `anthropic/claude-3.5-sonnet` | 200K | Reasoning |
| `google/gemini-pro-1.5` | 2M | Long context |

### 🧠 Deep (Premium)
Best for: Hardest problems, longest context

| Model | Context | Best For |
|-------|---------|----------|
| `anthropic/claude-3-opus` | 200K | Best reasoning |
| `openai/gpt-4-turbo` | 128K | Code, math |
| `meta-llama/llama-3.3-70b-instruct` | 128K | Open source premium |

---

## Free Models (27 total)

**Daily Limits:** 20 requests/day, 200 requests/day per IP (OpenRouter terms)

| Model | Provider | Context | Notes |
|-------|----------|---------|-------|
| `meta-llama/llama-3.3-70b-instruct:free` | Meta | 128K | Best free model |
| `qwen/qwen3-coder-480b:free` | Qwen | 32K | Great for code |
| `google/gemini-2.0-flash-exp:free` | Google | 1M | Longest context |
| `mistralai/mistral-small-3.1-24b-instruct-2506:free` | Mistral | 32K | Fast, capable |

---

## Provider Routing

When user makes request:

```
User Request → Quality Setting → Model Selection → OpenRouter API → Response
                                           ↓
                                    Our Server
                                           ↓
                              Deduct credits (provider + 5.5%)
```

### Per-User Isolation
- Each user has their own API key
- Requests tagged with user ID
- Usage tracked per-user in `llm_usage` table

---

## Security

### API Keys
- **Stored:** Encrypted in PostgreSQL with pgcrypto
- **Usage:** Server-side only, never exposed to users
- **Rotation:** Can be rotated via admin endpoint

### Request Flow
1. User authenticates with their Nexus API key
2. Server looks up their quality preference
3. Server selects model based on quality tier
4. Server makes request to OpenRouter (using OUR key)
5. Response returned to user
6. Credits deducted from user's balance

**User never sees our OpenRouter key.**

---

## Rate Limits (Credit-Based)

| Credits | Requests/Min |
|---------|--------------|
| 100+ | 1,000 |
| 1,000+ | 2,500 |
| 10,000+ | 5,000 |
| 100,000+ | 10,000 |

---

## Adding New Models

Models are fetched dynamically from OpenRouter's API:

```bash
curl "https://openrouter.ai/api/v1/models"
```

No code changes needed - new models appear automatically.

---

## Cost Examples

| Model | 1K Input | 1K Output | 1K Total |
|-------|----------|-----------|----------|
| gpt-4o-mini | $0.15 | $0.60 | $0.75 |
| claude-3.5-sonnet | $3.00 | $15.00 | $18.00 |
| gpt-4o | $2.50 | $10.00 | $12.50 |
| llama-3.3-70b (free) | $0.00 | $0.00 | $0.00 |

*Prices in USD, user pays +5.5%*
