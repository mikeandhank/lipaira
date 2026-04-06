# Lipaira Enterprise Guide

## Self-Hosted AI Agent Platform for the Enterprise

### Why Self-Hosted?

**Data Sovereignty** - Your data never leaves your infrastructure

**Compliance** - Meet GDPR, HIPAA, SOC2 requirements with your own controls

**Cost Control** - One-time deployment + API costs, no per-user licensing

**Customization** - Full access to modify prompts, tools, and workflows

**Offline Operation** - Run entirely on-premise with no internet required

## Security Operatorure

### Encryption at Rest
- **Database:** PostgreSQL with pgcrypto (AES-256-CBC) for sensitive columns
- **API Keys & Secrets:** Encrypted before storage
- **Full-Disk Encryption:** Recommended via LUKS or cloud provider volume encryption

### Network Security
- All services behind Traefik reverse proxy
- TLS termination at gateway
- Optional: VPN-only access for production deployments

### Access Control
- Role-based access control (RBAC): Admin, Developer, User, Viewer
- JWT authentication with refresh tokens
- API key management per user

## Deployment Options

### Single-Server (Recommended for SMB)
- Minimum: 4 CPU, 16GB RAM, 100GB SSD
- Includes: PostgreSQL, Redis, Ollama, API, Web UI

### Cluster Deployment (Enterprise)
- Separate database server (PostgreSQL primary + replica)
- Redis cluster for pub/sub
- Multiple API workers (Celery)
- GPU-accelerated inference nodes (vLLM)

### Cloud Providers
- AWS EC2 / GCP Compute Engine / Azure VM
- DigitalOcean Droplet (2TB+ recommended)
- Hetzner, Linode, etc.

## Compliance Guidance

### SOC 2
1. Deploy on isolated infrastructure
2. Enable full-disk encryption at host level
3. Configure audit logging retention (90+ days)
4. Implement RBAC with named user accounts

### GDPR
- Data stays on user's infrastructure (meets data residency requirements)
- User deletion removes all PII from database
- No third-party data processing

### HIPAA
- Deploy on private network (VPN required)
- Enable PostgreSQL encryption at rest
- Configure audit logging for all data access

## Enterprise Support

### Whats Included
- Deployment assistance
- Custom agent templates
- Security hardening review
- Integration support (SSO, webhooks)

### Contact
Email: support@nexusos.ai (placeholder)

## Pricing

- Free: Individual developers - sh
- Pro: Small teams (5 users) - 9 one-time
- Enterprise: Full organization - Custom

*Prices include deployment support. Cloud infrastructure costs separate.*

## Migration Path

Already using cloud AI agents? Lipaira provides:
1. Export tools for conversation history
2. API compatibility layer for existing integrations
3. Gradual migration (run both in parallel)

---

For security hardening specifics, see SECURITY.md
