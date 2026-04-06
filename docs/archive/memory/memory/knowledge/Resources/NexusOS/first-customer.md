# First Customer Profile

## Who

**"Alex" - Solo developer / small agency**

- Runs a one-person dev shop or agency
- Builds AI-powered automation for 2-5 SMB clients
- Currently using Claude Code, OpenClaw, or custom LangChain agents
- Makes $3-8K/month from client work
- Technically competent but not an infrastructure engineer

## What Alex Knows How to Do

- Write Python/Node.js code
- Deploy to VPS or cloud
- Configure API keys and prompts
- Debug agent behavior
- SSH into servers

## What Alex Doesn't Know How to Do

- Build persistent memory systems from scratch
- Maintain vector databases in production
- Handle security hardening for AI agents
- Set up model failover without writing custom code

---

## Potential Customer 2: "Marcus" - Indie Hacker

### Profile
- Builds AI-powered SaaS products
- Uses LangChain, CrewAI, or custom agents
- Needs memory that survives deployments
- Price-sensitive but will pay for reliability

### Pain Points
- LangChain memory resets between sessions
- No built-in persistence
- Wasting time rebuilding context

### What Marcus Needs
- Drop-in API for persistent memory
- Simple deployment (Docker)
- Clear docs for integration

---

## Potential Customer 3: "Team DevShop" - Small Team

### Profile
- 2-5 person dev team
- Building AI features for client projects
- Multiple agents across different tasks
- Some infrastructure capability

### Pain Points
- No shared memory across agent instances
- Context lost when switching between projects
- Client projects require consistent memory

### What Team DevShop Needs
- Team memory with access control
- Shared context across agents
- Self-hosted option for client data privacy

## What NexusOS Needs to Be for Alex

### Must Have (to use without help):
1. **One-command install** - `curl -sL nexusos.sh | bash` or `docker run nexusos`
2. **Works with existing agents** - Minimal config to point their agent to NexusOS memory
3. **Clear docs** - "Add these 3 lines to your agent code"
4. **Persistent from day one** - No setup required for core memory to work
5. **Self-healing** - Doesn't crash if one component fails

### Nice to Have (will pay for later):
- Monitoring dashboard
- Usage metrics
- Pre-built integrations for common stacks

## How This Flows to v1 Requirements

| Alex's Need | v1 Requirement |
|-------------|----------------|
| One-command install | Docker-compose deploy, simple config |
| Works with existing agents | MCP server integration (not custom code) |
| Clear docs | README with 5-minute setup |
| Persistent from day one | Working LanceDB (✓ already done) |
| Self-healing | Communication reliability, model failover |

## What NOT to Build for v1

Based on Alex:
- ❌ Custom agent UI - he has his own
- ❌ SaaS billing - not ready for multi-tenant
- ❌ Enterprise SSO - he uses password auth
- ❌ Complex dashboard - he'll check logs

---

_Last updated: 2026-03-13_
