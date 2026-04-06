# OpenClaw Agent Onboarding - Critical Processes

**For new OpenClaw instance. Last updated: 2026-04-05**

---

## CI/CD Pipeline

**NEVER use manual docker cp, scp, or docker exec to modify code on the server.** Always commit and push - let CI/CD deploy.

### The Flow
1. Make changes locally (edit files in `/data/.openclaw/workspace/`)
2. Commit: `git add . && git commit -m "description"`
3. Push: `git push origin main`
4. GitHub Actions automatically deploys:
   - SSH's to EC2 (3.147.192.198)
   - Pulls latest from git
   - Builds Docker image
   - Restarts containers

### Files
- GitHub workflow: `.github/workflows/deploy.yml`
- Docker build directory: `/home/ec2-user/lipaira-build/`
- Docker compose: `/home/ec2-user/nexusos/docker-compose.yml`

### EC2 Access
```bash
ssh -i /data/.ssh/id_ed25519 ec2-user@3.147.192.198
```

---

## Code Writing Protocol

**Standing order from Michael. Must follow for ALL new code.**

1. **Write the contract** (10-15 lines): purpose, inputs, outputs, failure mode, verification test, where it's wired
2. **Paste to Mike** for Claude review
3. **Get approval** before implementing
4. **After implementing**, run the verification test
5. **Paste the raw output** — not a summary
6. **Confirm with grep** that it's wired into the running server

**No component is "done" until step 6 passes.**

---

## Lipaira Project Structure

### Key Directories
- `/data/.openclaw/workspace/server_full.py` - Main API server
- `/data/.openclaw/workspace/lipaira-client/` - Client SDK
- `/data/.openclaw/workspace/lipaira-web/` - React frontend
- `/data/.openclaw/workspace/skills/` - Agent skills (restaurant, crm, grocery, etc.)
- `/data/.openclaw/workspace/*.py` - Supporting modules

### Services (Docker)
- **lipaira-api** - Main Flask API (port 80 internally)
- **lipaira-web** - React frontend
- **lipaira-postgres** - PostgreSQL database
- **lipaira-redis** - Redis cache
- **traefik** - Reverse proxy (ports 80/443)

### URLs
- Frontend: https://lipaira.ai
- API: https://api.lipaira.ai
- Health: https://api.lipaira.ai/health

---

## Dependencies to Fix

The server currently has issues that need investigation:

1. **Database connection** - DATABASE_URL in compose points to compose postgres which appears empty. Original working DB may have been external (RDS or different instance).

2. **Network routing** - Traefik returns 404 when proxying to lipaira-api container. Internal container works but external requests fail.

3. **Database migrations** - Tables like `users`, `api_keys`, `workflows` don't exist in current DB. Need to run migrations.

---

## Verification Commands

After any fix:
```bash
# Test health endpoint
curl https://api.lipaira.ai/health

# Test from inside container
ssh -i /data/.ssh/id_ed25519 ec2-user@3.147.192.198
docker exec lipaira-api curl localhost:8080/health

# Check logs
docker logs lipaira-api --tail 50
```

---

## What Was Being Worked On

**Block 3 Features (In Progress):**
- Item 7: Microsoft Outlook OAuth
- Item 8: Web search/fetch skills
- Item 9-14: Additional integrations (push notifications, pattern detection, restaurant, crm, grocery, discord, github)

**Known Issues:**
- pywebpush import fixed (was wrong package name)
- Route registration cascade failure fixed (individual try/except)
- Database needs restore or migrations run

---

## Contact
- Michael Beal - Telegram: 8643045688
- EC2 SSH key: `/data/.ssh/id_ed25519`
