# Working Memory - survives session restarts
# Auto-loaded on session start, auto-saved on session end

## Current Context
- User: Michael Beal
- Project: Lipaira (Self-hosted AI Agent OS) - renamed from NexusOS
- Lipaira spec: 6,014 lines in GitHub
- Codebase audit completed
- Server: https://api.lipaira.ai (healthy)

## Active Priorities
1. Follow Code Writing Protocol (see below)
2. Don't delete lipaira-client/provisioner.py (Block 2 critical)
3. Register Twilio routes (already written, just not wired)

## CODE WRITING PROTOCOL (Standing Order - 2026-04-04)

Before writing any new code:
1. Write the contract (10-15 lines): purpose, inputs, outputs, failure mode, verification test, where it's wired
2. Paste to Mike for Claude review
3. Get approval before implementing
4. After implementing, run the verification test
5. Paste the raw output — not a summary
6. Confirm with grep that it's wired into the running server

**No component is "done" until step 6 passes.**

## Critical Files - DO NOT DELETE
- `lipaira-client/provisioner.py` - Block 2 critical
  - Multi-Agent Orchestration ✅ /api/agents
  - Redis + Celery async ✅ Built
  - Usage Analytics ✅ /api/metrics ($2.77, 98 reqs, 3345 tokens)
  - Webhook System ✅ /api/webhooks
- Server 187.124.150.225:8080 v6.0.0 running
- SSH access blocked - need credentials for deploy
- Swagger docs code ready but not deployed
- Security audit completed (2026-03-16)
  - All CRITICAL + HIGH fixes deployed (15 modules)
  - API versioning + observability added (2026-03-16 22:40)
  - GPU inference + plugin SDK added (2026-03-16 22:42)

---

# Auto-Capture Tags
# Add important context here as it happens
# Format: [timestamp] tag: content
