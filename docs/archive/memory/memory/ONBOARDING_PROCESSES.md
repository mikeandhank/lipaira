# Lipaira Onboarding - Process Guide

**For the new agent:** This file explains how to work on Lipaira without breaking things.

---

## CI/CD Pipeline (MANDATORY)

**Never bypass this flow. Ever.**

### The Process
1. Make changes locally (edit files in `/data/.openclaw/workspace/`)
2. Commit: `git add . && git commit -m "description"`
3. Push: `git push origin main`
4. GitHub Actions automatically deploys to EC2

### What NOT to do
- ❌ `docker cp` to copy files to running containers
- ❌ `docker exec` to modify code on EC2
- ❌ Manual `scp` or SSH edits
- ❌ Direct container restarts for code changes

### Why It Matters
- Manual edits break CI/CD (git pull conflicts)
- No audit trail of what changed
- Creates uncommitted state on server
- Breaks reproducibility

### Manual Fallback (ONLY if pipeline is broken)
```bash
# SSH to EC2
ssh -i /data/.ssh/id_ed25519 ec2-user@3.147.192.198

# Navigate to build dir
cd /home/ec2-user/lipaira-build

# Pull and build
git pull
docker build -t lipaira-api:latest .
docker rm -f lipaira-api
cd /home/ec2-user/nexusos
docker-compose up -d lipaira-api

# Restart Traefik
docker restart traefik
```

---

## Code Writing Protocol (MANDATORY)

**Standing order from Michael. Follow exactly.**

Before writing ANY new code:
1. **Write the contract** (10-15 lines):
   - COMPONENT name
   - PURPOSE
   - INPUT (parameters)
   - OUTPUT (return value)
   - IMPLEMENTATION notes
   - FAILURE MODE (what happens when it breaks)
   - VERIFICATION TEST (how to prove it works)
   - WHERE IT'S WIRED (file + line)

2. **Paste to Mike** for Claude review

3. **Get approval** before implementing

4. **After implementing**, run the verification test

5. **Paste the raw output** — NOT a summary, the actual output

6. **Confirm with grep** that it's wired into the running server

**No component is "done" until step 6 passes.**

---

## Current Infrastructure

| Service | URL | Notes |
|---------|-----|-------|
| **EC2** | 3.147.192.198 | SSH with id_ed25519 |
| **API** | https://api.lipaira.ai | Behind Traefik |
| **Frontend** | https://lipaira.ai | React app |
| **Database** | PostgreSQL on docker compose | |
| **Redis** | Docker compose | |

### Docker Networks
- `nexusos_lipaira-net` - Main network for all services
- All containers must be on this network for Traefik routing

### Critical Files
- `docker-compose.yml` - Service definitions
- `server_full.py` - Main API server
- `Dockerfile` - Container build

---

## Common Issues & Solutions

### Server returning 404
- Check if container is running: `docker ps | grep lipaira`
- Check logs: `docker logs lipaira-api`
- Verify Traefik can reach: `curl localhost:8080/health` from within Traefik container

### Database issues
- DATABASE_URL format: `postgresql://user:pass@host:port/dbname`
- Compose service name: `postgres` (resolves to container)

### Dependencies not installing
- Check if import name matches pip package name
- Example: `pywebpush` package → import as `from pywebpush import ...`

---

## Verification Tests (Run these after ANY change)

```bash
# 1. Health check
curl -s https://api.lipaira.ai/health

# 2. Push routes (if implemented)
curl -s https://api.lipaira.ai/api/push/public-key

# 3. Check logs for errors
docker logs lipaira-api 2>&1 | grep -i error
```

---

## Big Picture (What We're Building)

**Lipaira** - Self-hosted AI Agent OS with Inner Life
- Target: Privacy-sensitive professionals, SMBs
- Revenue model: 5.5% fee on credit purchases
- Key features: Multi-agent orchestration, memory system, integrations (Gmail, QuickBooks, etc.)
- Self-hosted first (data stays on user's machine)

---

_Last updated: 2026-04-05_
