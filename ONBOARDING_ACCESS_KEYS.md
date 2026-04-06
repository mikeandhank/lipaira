# API Keys & Credentials - DO NOT COMMIT TO REPO
**For new OpenClaw instance. Last updated: 2026-04-05**

---

## AWS (Production EC2)

| Secret | Location | Purpose |
|--------|----------|---------|
| AWS Access Key | EC2 IAM Role | EC2 has IAM role with permissions for Secrets Manager, S3, etc. |
| Database URL | docker-compose.yml or AWS Secrets Manager | PostgreSQL connection string |
| All Provider Keys | AWS Secrets Manager `/lipaira/*` | 33+ LLM provider API keys |

### AWS Secrets Manager Keys (to load)
```
/lipaira/anthropic-api-key
/lipaira/OpenRouter_API_Key
/lipaira/Google_OAuth_Client_ID
/lipaira/Google_OAuth_Client_Secret
/lipaira/MICROSOFT_CLIENT_ID
/lipaira/MICROSOFT_CLIENT_SECRET
/lipaira/QuickBooks_Client_ID
/lipaira/QuickBooks_Client_Secret
/lipaira/Stripe_Secret_Key
/lipaira/Stripe_Webhook_Secret
```

### EC2 Instance
- **Host:** 3.147.192.198
- **SSH:** `ssh -i /data/.ssh/id_ed25519 ec2-user@3.147.192.198`
- **Region:** us-east-2

---

## GitHub

- **Token:** (in runtime memory - check LastPass or 1Password)
- **Repo:** https://github.com/mikeandhank/nexus-ai
- **Permissions:** repo, workflow (for CI/CD deploy)

---

## Domain (Cloudflare)

- **Domain:** lipaira.ai
- **Proxy:** Cloudflare proxying lipaira.ai and api.lipaira.ai
- **SSL:** Let's Encrypt via Traefik (auto-renewal)

---

## OAuth Providers

### Google Cloud Console
- **Client ID:** 105139873132-drqfdk51ebj80kd51nhb5ihbj17f6l42.apps.googleusercontent.com
- **Client Secret:** (check Secrets Manager or runtime memory)
- **Scopes:** gmail.send, gmail.readonly, calendar.events, calendar.readonly, drive.file, contacts.readonly

### Microsoft Azure AD
- **Client ID:** (check AWS Secrets Manager)
- **Client Secret:** (check AWS Secrets Manager)
- **Redirect URI:** https://lipaira.ai/api/auth/microsoft/callback

### QuickBooks
- **Client ID:** (check AWS Secrets Manager)
- **Client Secret:** (check AWS Secrets Manager)
- **Redirect URI:** https://lipaira.ai/api/auth/quickbooks/callback

---

## Payment (Stripe)

- **Secret Key:** (in AWS Secrets Manager)
- **Webhook Secret:** (in AWS Secrets Manager)
- **Product:** Credit purchases with 5.5% fee

---

## External Services

| Service | Key Location | Purpose |
|---------|--------------|---------|
| Resend | AWS Secrets Manager | Transactional email |
| Twilio | AWS Secrets Manager | SMS approval flow |
| OpenRouter | AWS Secrets Manager | LLM routing |

---

## Secrets NOT in Repo

**Critical:** Never commit API keys, tokens, or secrets to git. They go in:
- AWS Secrets Manager (preferred)
- OpenClaw runtime memory
- LastPass / 1Password (for manual reference)

---

## Loading Secrets in Code

```python
import boto3
import os

secrets_client = boto3.client('secretsmanager', region_name='us-east-2')

def get_secret(secret_name):
    response = secrets_client.get_secret_value(SecretId=secret_name)
    return response['SecretString']

# Usage
anthropic_key = get_secret('lipaira/anthropic-api-key')
```

---

## Contact
Michael Beal - Telegram: 8643045688
