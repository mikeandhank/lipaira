# Lipaira Client Container

**Each client gets their own isolated Docker container.**

## Why Per-Client Containers?

| Security Benefit | Description |
|-----------------|-------------|
| Filesystem isolation | Each client's files are completely separate |
| Process isolation | No cross-client process access |
| Resource limits | Guaranteed CPU/memory per client |
| Network isolation | Clients can't reach each other's containers |
| Failure isolation | One compromised container ≠ all compromised |

## Operatorure

```
┌─────────────────────────────────────────────────────────────┐
│                    Lipaira Infrastructure                    │
├─────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐      │
│  │ Client A     │   │ Client B     │   │ Client C     │      │
│  │ Container    │   │ Container    │   │ Container    │      │
│  │              │   │              │   │              │      │
│  │ - Agent      │   │ - Agent      │   │ - Agent      │      │
│  │ - Sandbox    │   │ - Sandbox    │   │ - Sandbox    │      │
│  │ - Files      │   │ - Files      │   │ - Files      │      │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘      │
│         │                  │                  │               │
│         └──────────────────┼──────────────────┘               │
│                            ▼                                   │
│              ┌────────────────────────┐                       │
│              │   API Gateway          │                       │
│              │   (billing, auth)      │                       │
│              └───────────┬────────────┘                       │
│                          │                                      │
│              ┌───────────┴────────────┐                       │
│              ▼                         ▼                       │
│     ┌───────────────┐        ┌───────────────┐               │
│     │  Credit       │        │  LLM Router   │               │
│     │  Billing      │        │  (OpenRouter) │               │
│     └───────────────┘        └───────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

## Provisioning Flow

### 1. User Signs Up
```
POST /api/clients/provision
{ "user_id": "xxx", "email": "user@email.com" }
```

### 2. System Creates Container
```python
provisioner.provision(
    user_id="user123",
    user_email="user@email.com",
    max_memory_mb=512,
    max_cpu=0.5
)
```

### 3. Container Starts
- Image: `lipaira/client:latest`
- Network: `lipaira-internal`
- Resources: 512MB RAM, 50% CPU
- Volume: `/home/client/data`

### 4. User Connects
- Internal: `http://lipaira-client-xxx:8081`
- External: Via API gateway (proxied)

## API Endpoints (Inside Container)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/agent/execute` | POST | Execute agent task |
| `/agent/sessions` | GET | List sessions |
| `/agent/sessions/<id>` | GET | Get session |
| `/agent/sessions/<id>` | DELETE | Delete session |
| `/config` | GET | Client config |
| `/files` | GET/POST/DELETE | File storage |
| `/sandbox/test` | POST | Test sandbox |

## Resource Limits

Applied automatically per client:

| Resource | Default | Configurable |
|----------|---------|--------------|
| Memory | 512MB | Yes |
| CPU | 50% (0.5 cores) | Yes |
| Max execution | 300s | Yes |
| Network | Outbound only | Yes |

## Security Features

1. **Non-root user** - Container runs as `client` user
2. **Sandbox** - All agent code runs in restricted environment
3. **No plugin marketplace** - Eliminates supply chain attacks
4. **API key isolation** - Keys never touch client container
5. **Network isolation** - Internal network, clients can't reach each other

## Building

```bash
cd lipaira-client
docker build -t lipaira/client:latest .
```

## Testing Locally

```bash
# Build
docker build -t lipaira/client:latest .

# Run locally
docker run -d \
  --name lipaira-test \
  -e LIPAIRA_CLIENT_ID=test123 \
  -e LIPAIRA_USER_EMAIL=test@test.com \
  -e LIPAIRA_API_URL=http://host.docker.internal:8080 \
  -p 8081:8081 \
  lipaira/client:latest

# Test
curl http://localhost:8081/health
```

## Files

```
lipaira-client/
├── Dockerfile         # Container image definition
├── agent.py           # Agent runtime
├── sandbox.py         # Kernel sandbox
├── provisioner.py     # Client provisioning API
├── requirements.txt   # Python dependencies
└── README.md         # This file
```