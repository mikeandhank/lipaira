# Lipaira - AI Agent OS

**Secure AI agents accessible to everyone**

## Two Ways to Use Lipaira

### 1. Cloud (Recommended for Most Users)
**No installation required** — just sign up and start using.

```
lipaira.ai → Sign up → Use agent via web/iOS/Android
```

- Instant access
- We handle everything
- Non-technical friendly
- Pay us for credits

### 2. Self-Hosted (For Enterprise)
Deploy on your own VPS for full control.

```bash
curl -sSL https://lipaira.ai/install | sudo bash
```

- Run on your infrastructure
- Still connects to our server for billing
- Full customization
- For technical users/enterprises

---

## Why Lipaira?

| Feature | Lipaira | OpenClaw | Claude Cowork |
|---------|---------|----------|---------------|
| Hosted (no install) | ✅ | ❌ | ✅ |
| Self-hosted option | ✅ | ✅ | ❌ |
| Kernel sandbox | ✅ | ❌ | ❌ |
| No plugin attacks | ✅ | ❌ | ✅ |
| Mobile apps | ✅ (coming) | ❌ | ❌ |
| API key protection | ✅ | ❌ | N/A |

## Security Model

**All client interactions go through our server.**

1. **Maximum Security** — API keys never touch client device
2. **Maximum Flexibility** — Access via web, iOS, or Android  
3. **Complete Billing Control** — We see every LLM call
4. **Unified Experience** — Same interface across all platforms

## Billing

**We handle billing. Users buy credits from us.**

- Users purchase credits via web/iOS/Android apps
- LLM calls routed through our server
- We take 5.5% fee on all credit purchases
- BYOK (Bring Your Own Key): 5% fee on LLM costs

## Self-Hosted Installation

```bash
curl -sSL https://lipaira.ai/install | sudo bash
```

### After Install

```bash
# Start
sudo lipaira start

# Check status
sudo lipaira status
```

Get your API key from lipaira.ai dashboard, then access at `http://YOUR_SERVER_IP`

### Commands

| Command | Description |
|---------|-------------|
| `lipaira start` | Start all services |
| `lipaira stop` | Stop all services |
| `lipaira restart` | Restart |
| `lipaira status` | Show status |
| `lipaira logs` | View logs |
| `lipaira update` | Update to latest |

### Requirements (Self-Hosted)

- Ubuntu 20.04+ / Debian 11+ / RHEL 8+
- 2GB RAM minimum (4GB recommended)
- Docker
- Root access
- Internet connection to api.lipaira.ai for billing

## Security

- **No plugin marketplace** — eliminates supply chain attacks
- **Kernel sandbox** — malicious code can't escape
- **API keys never touch agent** — routed through secure layer
- **All billing through us** — we see every call

## Support

- Discord: https://discord.gg/lipaira
- Email: dev@lipaira.ai
- Docs: https://docs.lipaira.ai

## License

Proprietary - All rights reserved