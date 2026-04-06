# Lipaira SOC 2 + HIPAA Compliance Audit & Remediation Plan
**Date:** April 6, 2026
**Status:** NOT COMPLIANT — 6 CRITICAL findings
**Auditor:** Hank (internal)
**Review link:** https://github.com/mikeandhank/lipaira-specs/blob/main/COMPLIANCE_AUDIT.md

---

## Executive Summary

| Category | Status |
|---|---|
| Secrets Management | 🔴 CRITICAL — hardcoded credentials in code |
| Data Encryption (at rest) | 🔴 CRITICAL — PostgreSQL unencrypted; Redis no AUTH |
| Access Control / Auth | 🔴 CRITICAL — no user auth system |
| Audit Logging | 🔴 CRITICAL — fails silently |
| HIPAA / PHI Handling | 🔴 CRITICAL — PHI flowing, no BAA |
| Privacy / Consent | 🔴 CRITICAL — no privacy policy |
| Encryption (in transit) | 🟡 AMBER — TLS configured, no version enforcement |
| AWS / Vendor Management | 🟡 AMBER — BAA not signed |
| Data Isolation | 🟡 AMBER — fresh start opportunity |
| Incident Response | 🟡 AMBER — no tested backup/recovery |

**Overall posture: NOT COMPLIANT. Do not go live without resolving critical items.**

---

## CRITICAL Findings

### 🔴 CRITICAL-1: Hardcoded Credentials (FIXED ✅)
> **Note: This finding has been remediated. Code pushed April 6, 2026.**

All hardcoded fallback credentials removed from `server_full.py`, `docker-compose.yml`, `audit_log.py`, `integrations/credential_store.py`. The following were removed:
- DB password: `2c27dd080c0a8f7b02dace074bd4cb77ba48cfb5`
- OpenRouter API key: `sk-or-v1-28fa3935df40bc0455be8143f0c95391a0fe1270`
- Google OAuth secret: `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`
- Internal auth key: `lipaira-internal`
- DB fallback: `nexusos:ChangeMe123!@postgres`
- Encryption key: `default-fallback`

**Remaining action:** Rotate the above credentials in AWS Secrets Manager and Google Cloud Console — assume all were compromised.

---

### 🔴 CRITICAL-2: No User Authentication System

**Finding:** No `/register`, `/login`, `/logout` routes. No password hashing at auth layer. No RBAC. Flask cookie sessions with no expiration enforcement. Every API caller has full access.

**What SOC 2 requires:** Secure access controls, unique user identification, automatic logoff.
**What HIPAA requires:** Unique user IDs, emergency access procedures, automatic logoff.

**Contract (C4):** Written. See `COMPLIANCE_FIXES_CONTRACTS.md` — Contract C4: User Authentication System.
- `POST /api/auth/register` → bcrypt password, JWT (24h), verification email
- `POST /api/auth/login` → JWT (24h) + refresh token (30 days, httpOnly cookie)
- `POST /api/auth/logout` → invalidates refresh token
- 5 failed logins → 15-minute lockout
- RBAC: `user` vs `admin` vs `operator` roles

**Verification:** Register → get JWT → `/api/auth/me` → data returned → logout → 401.

---

### 🔴 CRITICAL-3: PHI Flowing Through System With No Controls

**PHI present in:**
- Email content (Gmail, Outlook — full email text stored in memory_nodes)
- QuickBooks data (invoice amounts, client PII, financial data)
- Calendar data (appointment details)
- Twilio SMS content
- Memory nodes (arbitrary facts including health, family, financial status)

**What's missing:**
1. **AWS BAA** — Required before PHI touches AWS. Not in place.
2. **Encryption at rest** — PostgreSQL volume is NOT encrypted.
3. **Access controls** — No user isolation. No minimum necessary access.
4. **PHI audit trail** — Audit logger fails silently.
5. **TLS enforcement** — TLS configured but no version lock.
6. **Breach notification** — 60-day requirement. No procedure exists.

**HIPAA requires a BAA with AWS** — go to AWS Artifact → HIPAA BAA template → accept. This is a hard blocker before any PHI-adjacent integration (email, QB, calendar) can be used.

---

### 🔴 CRITICAL-4: Audit Logger Silently Fails

**Finding:** `audit_log.py` wraps all writes in `try/except` that only logs a warning. If PostgreSQL is down, audit events disappear with no alert, no retry, no fallback.

**Contract (C2):** Written. See `COMPLIANCE_FIXES_CONTRACTS.md` — Contract C2: Fail-Safe Audit Logging.
```
audit_event → [primary: DB write, retry 3x with backoff]
             → [fallback: /var/log/lipaira/audit/YYYY-MM-DD.jsonl]
             → [if both fail: logger.error → triggers alerting]
```
File-based fallback is append-only, mounted from host (survives container restart).

**Verification:** Stop PostgreSQL → execute skill → `/var/log/lipaira/audit/audit.log` has event within 2 seconds → restart DB → replay job picks up buffered events.

---

### 🔴 CRITICAL-5: Redis With No AUTH

**Finding:** Redis running without a password on the Docker network. Cached sessions, tokens, rate limit counters are readable by any container on `lipaira-net`.

**Contract (C3):** Written. See `COMPLIANCE_FIXES_CONTRACTS.md` — Contract C3: Enable Redis AUTH.
- `REDIS_PASSWORD` loaded from AWS Secrets Manager at startup
- All `redis.Redis()` calls include `password=os.environ['REDIS_PASSWORD']`
- Redis fails-closed if password not set (no silent fallback)

**Verification:** `redis-cli` without password → `AUTH failed`. With password → `PING` → `PONG`.

---

### 🔴 CRITICAL-6: Encryption Key Uses Fixed Salt

**Finding (`encryption.py`):**
```python
salt = b'nexusos-salt-v1'  # Fixed salt — all users share this
```
PBKDF2 with a fixed, known salt means anyone with the dev key (`dev-key-do-not-use-in-prod`) can derive the exact encryption key for every user. Also, `integrations/credential_store.py` had `'default-fallback'` as the encryption key — a known string.

**Contract (C5):** Written. See `COMPLIANCE_FIXES_CONTRACTS.md` — Contract C5: Encryption Key Derivation.
- Replace fixed salt with per-user unique salt via HKDF: `HKDF-SHA256(user_id, salt=device_fingerprint, info=b'lipaira-key-v1')`
- Production requires `ENCRYPTION_KEY` env var — raises `ValueError` if missing
- Device fingerprint column added to `users` table

**Verification:** Encrypt same plaintext for two users → different ciphertexts → decrypt with wrong user's key → `Fernet.InvalidToken`.

---

## Remediation Roadmap

### Phase 1 — Next 30 Days

| # | Action | Owner | Status |
|---|---|---|---|
| C1 | Remove hardcoded fallbacks | Hank | ✅ DONE |
| C2 | Fail-safe audit logging | Hank | Pending |
| C3 | Enable Redis AUTH | Hank | Pending |
| C4 | Build user auth system | Hank | Pending |
| C5 | Fix encryption key derivation | Hank | Pending |
| C6 | Data deletion endpoint | Hank | Pending |
| C7 | Credential rotation runbook | Hank | Pending |
| — | Rotate OpenRouter key (AWS console) | **Michael** | Needed |
| — | Rotate Google OAuth secret (Google Cloud) | **Michael** | Needed |
| — | Sign AWS HIPAA BAA | **Michael** | Needed |
| — | Enable EBS encryption (AWS console) | **Michael** | Needed |
| — | Fix EC2 SSH access | **Michael** | Blocked |
| — | Privacy policy + ToS | **Michael** | Needed |

### Phase 2 — 30-90 Days (SOC 2 Type I Readiness)

- Build RBAC (user/admin/operator roles)
- Add MFA (TOTP, required for admin)
- Immutable audit trail (CloudWatch Logs)
- Secrets rotation automation
- Network segmentation (lock down Postgres/Redis)
- Penetration test (OWASP ZAP)
- Incident response plan
- Backup/restore tested (RTO/RPO documented)
- Vendor DPAs signed (OpenRouter, Twilio, Resend, Stripe)
- Per-user data isolation (schema-based for free, dedicated DB for paid)

### Phase 3 — 90 Days to 18 Months (HIPAA Ready)

- Full PHI classification and assessment
- PHI access logging (every read/write to PHI-bearing tables)
- Column-level encryption (PostgreSQL pgcrypto for PHI columns)
- AWS KMS for key management
- Quarterly access reviews
- Security awareness training documentation
- SOC 2 Type I audit (e.g., A-LIGN, Vanta, Secureframe)
- HIPAA risk assessment
- Breach notification procedure (tested)

---

## Contract Status Summary

| Contract | Description | Status |
|---|---|---|
| C1 | Remove hardcoded fallbacks | ✅ DONE |
| C2 | Fail-safe audit logging | 📋 Pending |
| C3 | Enable Redis AUTH | 📋 Pending |
| C4 | Build user auth | 📋 Pending |
| C5 | Fix encryption key derivation | 📋 Pending |
| C6 | Data deletion endpoint | 📋 Pending |
| C7 | Credential rotation runbook | 📋 Pending |
| Block 3-7 | Microsoft Outlook | 📋 Pending |
| Block 3-9 | Square | 📋 Pending |
| Block 3-10 | Slack | 📋 Pending |
| Block 3-11 | Grocery ordering | 📋 Pending |
| Block 3-12 | Restaurant reservations | 📋 Pending |
| Block 3-13 | PWA + push | 📋 Pending |
| Block 3-14 | Pattern → workflow | 📋 Pending |
| Block 4-16 | Event queue | 📋 Pending |
| Block 4-17 | Anticipatory scheduler | 📋 Pending |
| Block 4-18 | Federated intelligence | 📋 Pending |
| Block 4-19 | Local model (Ollama) | 📋 Pending |
| Block 4-20 | Voice interface | 📋 Pending |

---

## Key Compliance Notes for Future Development

1. **Email, QB, Twilio = PHI-adjacent** — These integrations cannot be marketed as HIPAA-compliant until Phase 3 is complete. Keep this explicit in the privacy policy.

2. **Federated intelligence (Block 4-18)** is the highest privacy risk in the roadmap. It requires the most careful design — start the privacy review before writing any code for it.

3. **The missing DB tables are a clean slate.** Design the schema with HIPAA controls from day one: PHI isolation, column-level encryption, immutable `created_at`/`updated_at` audit columns on every table.

4. **AWS BAA is a hard blocker** before any PHI touches AWS. Even if we don't market as HIPAA-compliant at launch, the BAA should be signed now — it's free and takes 10 minutes. Without it, we have no legal basis to process PHI on AWS.

---

## Files

| File | Location |
|---|---|
| Full audit | `lipaira-specs/COMPLIANCE_AUDIT.md` |
| Compliance contracts | `lipaira-specs/COMPLIANCE_FIXES_CONTRACTS.md` |
| Product contracts | `lipaira-specs/CONTRACTS_BLOCK3_BLOCK4.md` |
| Spec v6 | `lipaira-specs/LIPAIRA_SPEC_v6.md` |
| Spec v8 | `lipaira-specs/LIPAIRA_SPEC_v8.md` |
| Code | `mikeandhank/nexus-ai` |
