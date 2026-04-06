# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

## Infrastructure Notes

### Email (Gmail)
- Config: `~/.config/himalaya/config.toml`
- Issue: App password invalid as of 2026-03-13 (~9AM ET)
- Needs new app password from myaccount.google.com → Security → 2-Step → App passwords

### GitHub
- Token: (in memory - not in repo)
- Use for: Repo operations, issues

### Vercel
- Token: (in memory - not in repo)
- Use for: Deploying web apps, landing pages

### Notion API
- Key: (in memory - not in repo)
- Use for: HankV2 bot, workspace integration

### Hostinger
- Token: (in memory - not in repo)
- Use for: Domain/DNS management

### Resend
- API Key: (in memory - not in repo)
- Use for: Transactional email (waitlist signups)

### Lipaira Server (formerly NexusOS)
- Production: 187.124.150.225 (port 22 SSH, root)
- Path: /opt/lipaira
- Version: 6.0.0 (confirmed working)
- Status: ALL Phase 1 features operational ✅
  - Multi-Agent Orchestration: /api/agents ✅
  - Redis + Celery (async): Built 2026-03-15 ✅
  - Usage Analytics: /api/metrics working ✅
  - Webhook System: /api/webhooks implemented ✅
- Web UI: /ui working ✅
- Issue: GitHub Actions deploy fails (secrets not configured)

## What's Been Tried

- Web search on AI agent platforms (Claude Code, LangGraph, AutoGen, CrewAI)
- OpenClaw docs deep dive (memory, tool-loop, concepts)
- Email auth failing - credential issue

---

_Last updated: 2026-03-19 (Renamed from NexusOS to Lipaira)_

---

## CI/CD Deployment Rule (2026-03-30)

**ALL changes to Lipaira must go through CI/CD:**

1. Make changes locally
2. Commit: `git add . && git commit -m "description"`
3. Push: `git push origin main`
4. GitHub Actions automatically deploys

**NEVER use docker cp, docker exec edits, or manual scp**

---

## Lipaira Current State (2026-03-30)

**EC2:** 3.147.192.198  
**API:** https://api.lipaira.ai  
**Frontend:** https://lipaira.ai  
**Network:** nexusos_lipaira-net (via compose mapping)

