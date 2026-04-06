# Lipaira — DNS & Website Integrations Spec

**Version:** 1.0  
**Date:** March 31, 2026  
**Status:** Draft — Strategic Review Before Building

---

# Vision

**Lipaira = Your entire office in your pocket.**

This spec enables Lipaira to manage a service business's entire digital presence:
- Domain & DNS (GoDaddy, Cloudflare, Namecheap)
- Website content (GoDaddy Website Builder, Squarespace)
- E-commerce (Shopify)

---

# Integrations

## 1. GoDaddy

- **Auth:** API Keys (Consumer Key + Consumer Secret)
- **Rate Limit:** 60 requests/minute
- **Capabilities:**
  - DNS record management (A, CNAME, TXT, MX, etc.)
  - Email sending setup (SPF, DKIM, DMARC)
  - Website builder page updates
  - Pricing section updates

## 2. Squarespace

- **Auth:** OAuth 2.0
- **Rate Limit:** 10 requests/second
- **Capabilities:**
  - Page content updates
  - Product/service pricing
  - Business hours updates

## 3. Shopify

- **Auth:** Admin API Access Token
- **Rate Limit:** 40 requests/second
- **Capabilities:**
  - Product pricing
  - Order creation (invoicing)
  - Inventory tracking

---

# Database Schema

```sql
-- Extended user_integrations table
ALTER TABLE user_integrations 
ADD COLUMN IF NOT EXISTS provider_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS domain VARCHAR(255),
ADD COLUMN IF NOT EXISTS site_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS rate_limit INTEGER,
ADD COLUMN IF NOT EXISTS last_api_call TIMESTAMP;

-- DNS records managed by Lipaira
CREATE TABLE dns_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    record_type VARCHAR(10) NOT NULL,
    name VARCHAR(255) NOT NULL,
    value TEXT NOT NULL,
    ttl INTEGER DEFAULT 3600,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Sync log for auditing
CREATE TABLE integration_sync_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

# Core Components

## 1. IntegrationCredentialStore

Manages all provider credentials with consistent encryption (AWS KMS).

```python
class IntegrationCredentialStore:
    PROVIDER_CONFIG = {
        "godaddy": {"type": "registrar", "auth_method": "api_key", "rate_limit": 60},
        "squarespace": {"type": "website", "auth_method": "oauth", "rate_limit": 10},
        "shopify": {"type": "ecommerce", "auth_method": "access_token", "rate_limit": 40},
    }
```

## 2. RateLimiter + NetworkHandler

Handles external API calls with rate limiting, retry logic, and user-friendly errors.

## 3. IntegrationHandler

Wraps all integration calls with consistent error handling.

## 4. IdempotencyManager

Prevents duplicate DNS records or products.

---

# Build Order

1. Database migrations (extend user_integrations)
2. IntegrationCredentialStore class
3. RateLimiter + NetworkHandler
4. IdempotencyManager
5. GoDaddy adapter (DNS only first)
6. Squarespace adapter
7. Shopify adapter
8. API endpoints for each
9. Dashboard UI for connection management

---

# Open Questions (See Strategic Review)

- How does this fit with the Operator architecture?
- What happens when credentials expire?
- How do we handle partial failures in multi-platform updates?
- What's the pricing model for integrations?

---

# Related Specs

- [SPEC-OPERATOR-ARCHITECTURE.md](./SPEC-OPERATOR-ARCHITECTURE.md) - The central orchestrator
- [SPEC-TASK-SYSTEM.md](./SPEC-TASK-SYSTEM.md) - Unified task representation
- [SPEC-CONNECTION-UI.md](./SPEC-CONNECTION-UI.md) - Integration management UI