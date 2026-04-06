# NexusOS Changelog

All notable changes to this project will be documented in this file.

## [0.3.1] - 2026-03-29

### Fixed
- **OAuth callback routing** - Google OAuth redirect_uri now correctly routes through nginx to the API backend instead of hitting the frontend. Added `/api/*` proxy rule to nginx config.
- **Encryption.py import** - Fixed wrong PBKDF2 class import in encryption module.

### Technical Note
- When using frontend + backend architecture with OAuth, the redirect_uri must point to the backend API, not the frontend. The nginx proxy handles routing `/api/*` requests to the API container.

---

## [0.3.0] - 2026-03-16

### Added
- **Easy-install package** - One-command deployment: `curl -sL https://get.nexusos.cloud | bash`
- **Extended tools** - browser_tool.py, web_tool.py, messaging_tool.py, node_tool.py, email_tool.py, cron_tool.py
- **LLM Integration Fix** - Pulled 4 Ollama models (llama3, mistral, phi3, codellama); llama3 now default
- **Tier 1 + Tier 2 Complete** - All 7 critical blockers deployed:
  - Database migrations, kernel syscall filter, agent trigger chains
  - SIEM export, OAuth2/SSO, custom RBAC, SAML/SCIM
- **True OS Capabilities** - Process Manager, IPC System, Workflow Engine, SSO Login Page
- **Sandbox Isolation** - gVisor/LXC/seccomp-bpf
- **Usage Dashboard** - User-first stats with 5.5% fee transparent

### Security
- Third-party audit completed: Grade C+
- 5 CRITICAL findings: exposed IP/SSH, DB creds in docs, JWT HS256, no password complexity, TEXT primary keys
- 8 HIGH findings: no CSRF, open registration, no input sanitization, etc.
- Strategic response: Phase 1 (fix critical), Phase 2 (streaming/GPU), Phase 3 (DPA/SOC 2)

### Competitive Intelligence
- NemoClaw announced at GTC (Nvidia's enterprise OpenClaw)
- Window: 3-6 months before they mature
- Key gaps identified: streaming, GPU, model routing, community

---

## [0.2.0] - 2026-03-14

### Added
- **INTEGRATION.md** - Language-specific guides for OpenClaw, Claude Code, LangChain, AutoGen
- **Model failover system** - Automatic fallback to secondary LLM on failure
- **Enhanced status endpoint** - Shows current model, failure count, health
- **Customer research document** - Identified 3 customer profiles
- **Competitive analysis** - Detailed breakdown of Mem0, Letta, Zep, TeamLayer, Supermemory

### Improved
- Fixed duplicate `lancedb` dependency in package.json
- Updated BUILD.md with completed items checked off

### Changed
- Model failover configuration via environment variables
- Enhanced monitoring in status endpoint

---

## [0.1.0] - 2026-03-13

### Added
- Three-tier memory architecture (working, episodic, semantic)
- LanceDB integration for vector storage
- SQLite fallback for semantic memory
- MCP tool servers (filesystem, HTTP, process)
- Docker and docker-compose support
- README with quick start guide
- Health and status endpoints
- Persistence across server restarts

### Fixed
- LanceDB connection API (updated to new package)
- Async persist bug in memory-server.js
- mcp-http missing import

### Known Issues
- MCP servers not fully tested in Docker
- No OpenClaw integration yet (manual API calls only)
- Email authentication issue (external dependency)