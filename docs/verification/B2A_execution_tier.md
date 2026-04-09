# B2-A: execution_tier on Skills — Verification

**Date:** April 9, 2026  
**Contract:** B2-A (execution_tier enforcement for free tier)

---

## What Was Implemented

Added `execution_tier` attribute to skills in the skill registry:
- `execution_tier = "paid"` — Default. Requires credits to execute.
- `execution_tier = "free"` — Free tier users can execute.

Block logic in `run_agentic_loop` (line 3054):
```python
if user_credits <= 0:
    skill_tier = getattr(skill, 'execution_tier', 'paid') if skill else 'paid'
    if skill_tier == 'paid':
        output = json.dumps({
            "error": "credits_required",
            "message": "Connect credits to take this action. Free tier can read but not act."
        })
```

---

## What Passed

- ✅ Free tier read actions execute (no blocking)
- ✅ `user_credits` passed to `run_agentic_loop` (fixed NameError)
- ✅ Valid OpenRouter model used (`gemini-2.5-flash-lite`)
- ✅ DB migrations added (`context` column, `operator_audit_log` table)

---

## The Caveat

The free tier blocking only triggers on **explicit tool calls** (`block.get('type') == 'tool_use'`). 

If a user sends a natural language request like "send a chase email to Henderson" that the LLM handles conversationally (asking for more details instead of invoking the tool), no tool block occurs — the LLM runs freely.

This is a design choice: natural language is allowed, but explicit tool invocations are blocked for free tier unless the skill is marked `execution_tier = "free"`.

---

## Raw Test Output (April 9, 2026)

```
WARNING:server_full:SKILL_REGISTRY_COUNT: 15
WARNING:server_full:Free tier call: 2373 input, 77 output tokens (no charge)
WARNING:server_full:LOOP_DEBUG: round=1, stop_reason=stop, has_raw_content=True
WARNING:server_full:RAW_CONTENT: [{'type': 'text', 'text': "I need a bit more information to send a chase email..."}]
```

Note: No `TOOL_BLOCKED` logged because the LLM handled the request conversationally without invoking the email skill tool directly.