# Deploy Friction Log

_Testing NexusOS deployment as if seeing it for the first time_

---

## Test Context
- **Tester:** Hank (builder)
- **Time:** 2026-03-13, ~7:35 PM ET
- **Environment:** Linux sandbox (no Docker installed locally)

---

## Friction Points

### 1. NO README.md EXISTS
**Severity:** Critical
**Issue:** There's no README.md in the NexusOS folder. A new user has zero onboarding.
- Alex lands in the folder, sees BUILD.md (which is internal status, not user docs)
- No "Getting Started" instructions
- No explanation of what NexusOS does

---

### 2. Docker Not Available in Test Environment
**Severity:** Blocking (for this test, not necessarily for Alex)
**Issue:** `docker` command not found in sandbox
- Can't test docker-compose deployment
- Need Docker installed to proceed

---

### 3. docker-compose vs docker compose
**Severity:** Minor
**Issue:** Old command `docker-compose` vs new `docker compose`
- Modern Docker uses `docker compose` (subcommand)
- Need to document which to use

---

### 4. .env File Missing
**Severity:** High
**Issue:** docker-compose.yml references `.env` but file doesn't exist
- Users need to create it
- Should have `.env.example` with all required variables
- Need to explain what API keys are needed

---

### 5. Memory Server Port Mismatch
**Severity:** High
**Issue:** docker-compose exposes 4893 but memory-server.js default is different
- Need to verify ports align
- Or document which port to use

---

### 6. MCP Servers Not Started in Dockerfile
**Severity:** High
**Issue:** Dockerfile copies tools/ but doesn't start them
- memory-server.js starts, but MCP servers (mcp-filesystem, etc.) don't
- Need startup script or explicit ENTRYPOINT/CMD

---

### 7. No Health Check for MCP Servers
**Severity:** Medium
**Issue:** Docker healthcheck only tests memory-server
- MCP servers could fail silently
- Need comprehensive health check

---

### 8. Qdrant/Redis Marked Optional But Referenced
**Severity:** Low
**Issue:** docker-compose has qdrant/redis but LanceDB is used (not qdrant)
- Confusing - which one actually works?
- Memory server uses LanceDB, not qdrant

---

### 9. No Connection Instructions
**Severity:** Critical
**Issue:** No docs on how to connect OpenClaw/Claude Code to NexusOS
- What URL/port do they call?
- What API calls to use?
- Example code?

---

### 10. Node Modules in Repo
**Severity:** Medium
**Issue:** node_modules/ is committed (82MB+)
- Should be in .gitignore
- Makes repobloated

---

## Summary

| Friction | Severity | Blocks Alex? |
|----------|----------|--------------|
| No README | Critical | YES |
| .env missing | High | YES |
| No connection docs | Critical | YES |
| MCP servers not started | High | YES |
| node_modules committed | Medium | NO |

---

## What Alex Sees

1. Opens folder → sees BUILD.md (internal doc, not user-facing)
2. No getting started → doesn't know where to begin
3. Tries docker-compose → needs Docker, .env
4. Gets it running → doesn't know how to connect his agent

**Alex gives up at step 1 or 4.**

---

_Last updated: 2026-03-13_
