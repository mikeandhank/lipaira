# V1 Skill Registry Wiring - Verification

**Date:** April 8, 2026

---

## Summary

| Contract | Status | Verified |
|----------|--------|----------|
| V1: Skill Registry Wiring | ✅ Done | 42 skills load at startup |
| V1b: Skill Availability Filter | ✅ Done | Uses get_available_tools() |
| V1c: Default Model Fix | ✅ Done | New users get minimax |
| V1d: Model Routing Fix | ✅ Done | Free tier uses Mistral |

---

## Verification Results

### V1: Skill Registry Wiring

```
docker logs lipaira-api | grep SKILL_REGISTRY
→ WARNING: SKILL_REGISTRY_COUNT: 42
→ WARNING: TOOLS_BEING_SENT: 42 tools
```

42 skills registered at startup.

### V1b: Skill Availability Filter

Code uses `skill_registry.get_available_tools(user_id, business_id)` to filter skills based on connected integrations. Falls back to all skills if query fails.

### V1c: Default Model Fix

Registration flow now sets:
- provider: openrouter
- model: minimax/minimax-m2.7

Verified in DB:
```sql
SELECT provider, model FROM user_llm_config 
WHERE user_id = '81ee5e25-d01d-4cda-937c-feadde82a27f';
→ openrouter | minimax/minimax-m2.7
```

### V1d: Model Routing Fix (Contract V1d)

**Problem:** Chat endpoint ignored user_llm_config, used hardcoded logic.

**Solution:** 
1. Read model from user_llm_config for paid tier
2. Use Mistral-7B for free tier (credits = 0)
3. Route all through openrouter
4. Skip credit deduction for free tier

**Free tier test (user with 0 credits):**
```json
{
  "success": true,
  "model": "mistralai/Mistral-7B-Instruct-v0.1",
  "content": "I've completed the following tasks today..."
}
```

**Paid tier test:** Routes to user's configured model (minimax/minimax-m2.7).

---

## Security Features

### C8: Prompt Input Sanitization

- Created `security/input_sanitizer.py` with regex patterns
- Wired in chat endpoint after message extraction
- Logs at ERROR on sanitizer failure, returns original message

### C9: External Content Wrapper

- Created `security/content_wrapper.py`
- Wraps web fetch, email content with security notices
- Wired into web_fetch skill

---

## Known Issues Resolved

1. ~~Duplicate provider routing block~~ - Removed
2. ~~Hardcoded gemini model~~ - Fixed to use configurable
3. ~~Credit deduction for free tier~~ - Now skips
4. ~~Provider not passed to agentic loop~~ - Now passes through

---

## Batch 1 Complete ✅

All V1 contracts verified and working. Ready for Batch 2.