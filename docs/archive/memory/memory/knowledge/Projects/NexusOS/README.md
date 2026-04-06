# NexusOS — Enterprise AI That Remembers You

**Self-hosted AI agent operating system with persistent memory, multi-agent orchestration, and zero data exposure.**

> **The problem:** 95% of enterprise AI pilots stall because AI forgets everything between conversations. You get 30 minutes of brilliance, then... nothing.
> 
> **The solution:** NexusOS gives your AI agents memory that survives restarts—so they learn, adapt, and build context that compounds over time.

## Why NexusOS?

| Pain You're Feeling | What NexusOS Delivers |
|---------------------|----------------------|
| "My AI forgets everything when I restart" | Persistent memory that survives server reboots |
| "Context windows are too small" | Semantic memory = unlimited knowledge access |
| "My data is on someone else's server" | 100% self-hosted. Your data never leaves. |
| "Cloud AI keeps getting more expensive" | One-time deployment. No per-token fees. |
| "I need AI for my enterprise compliance" | SOC 2-ready with full audit trails |
| "CLI tools are hard for my team" | Beautiful web UI + powerful CLI |

## What Makes Us Different

### 🧠 Three-Tier Memory System
Most AI tools give you one conversation at a time. NexusOS gives you:
- **Working memory** — Current context, instant access
- **Episodic memory** — Past conversations, searchable
- **Semantic memory** — Structured knowledge, learned facts

Your agents get smarter over time, not just within a session.

### 🔒 Privacy-First Operatorure
Your competitors are training on your data. Your customers are trusting you with sensitive information. NexusOS ensures:
- Zero data exposure to third parties
- Full encryption at rest and in transit
- Complete audit trails for compliance
- You own everything, always

### 🤖 Multi-Agent Orchestration
Deploy teams of specialized AI agents that work together:
- Each agent has its own expertise
- Built-in collaboration protocols
- Coordinated goals, shared context
- Scale from one agent to hundreds

### ⚡ True Operating System
Not just another chatbot wrapper. NexusOS provides:
- Process management for AI tasks
- Inter-process communication
- Workflow orchestration
- Sandbox isolation for security

## Quick Start (5 Minutes)

```bash
# 1. Clone the repository
git clone https://github.com/nexusos-ai/NexusOS.git
cd NexusOS

# 2. Set up your environment
cp .env.example .env
# Edit .env and add your API keys

# 3. Deploy with Docker
docker compose up -d

# 4. Verify everything's running
curl http://localhost:4893/health
# Response: {"status":"healthy","memory_persistent":true}
```

**That's it.** Your self-hosted AI OS is running.

## Connect Your Existing Tools

### OpenClaw Integration
```json
{
  "memory": {
    "url": "http://localhost:4893"
  }
}
```

### Claude Code / Custom Integrations
```bash
# Start a conversation
curl -X POST http://localhost:4893/memory/working/start \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"my-session"}'

# Send a message
curl -X POST http://localhost:4893/memory/working/message \
  -H "Content-Type: application/json" \
  -d '{"content":"Remember this important detail","role":"user"}'

# End session (saves to persistent memory)
curl -X POST http://localhost:4893/memory/working/end

# Later: search your agent's memory
curl -X POST http://localhost:4893/memory/episodic/search \
  -H "Content-Type: application/json" \
  -d '{"query":"that important detail","limit":5}'
```

## Who This Is For

### 🏢 **Enterprises**
- Complete data control for compliance
- No vendor lock-in or subscription increases
- Custom deployment options (on-prem, cloud, hybrid)
- SOC 2, GDPR, HIPAA ready

### 🛡️ **Privacy-Sensitive Organizations**
- Healthcare, finance, legal, government
- Any organization handling sensitive data
- Companies with strict data residency requirements

### 👨‍💻 **Developers & Technical Teams**
- Open architecture, extensible
- Full API access
- CLI for automation
- Web UI for management

### 🚀 **AI-First Companies**
- Building AI products and need reliable infrastructure
- Need multi-agent orchestration
- Want memory that persists across sessions

## API Reference

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | System health check |
| `POST /memory/working/start` | Begin new conversation session |
| `POST /memory/working/message` | Add message to working memory |
| `POST /memory/working/end` | Save session to persistent memory |
| `POST /memory/episodic/search` | Search past conversations |
| `GET /memory/episodic/recent` | Retrieve recent memories |
| `GET /memory/semantic/knowledge` | Query structured knowledge |

## The Bottom Line

**Cloud AI keeps you dependent.** They're building moats with your data. Prices go up, features change, and you have no control.

**NexusOS keeps you free.** Your data stays yours. Your infrastructure runs your way. Your AI agents actually remember what you teach them.

**95% of enterprise AI pilots fail due to memory issues.** Don't be a statistic.

---

## Get Started

**Deploy in 5 minutes:**
```bash
git clone https://github.com/nexusos-ai/NexusOS.git
cd NexusOS
docker compose up -d
```

**Questions?** [Open an issue](https://github.com/nexusos-ai/issues) or [email us](mailto:hello@nexusos.cloud)

**Contribute?** We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

*NexusOS — Enterprise AI that remembers you.*