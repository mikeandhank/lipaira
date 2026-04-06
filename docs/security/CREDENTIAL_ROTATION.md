# Credential Rotation Runbook

> **Audience:** Operations / Security team  
> **Applies to:** Lipaira production environment on AWS EC2  
> **Last updated:** 2026-04-06

This runbook documents how to rotate each credential type in the Lipaira stack. After rotation, all services must be restarted to pick up new values.

---

## Credential Inventory

| Credential | Storage | Rotation Risk | Downtime |
|---|---|---|---|
| `DATABASE_URL` | AWS Secrets Manager + `.env` on EC2 | High — breaks all connections if wrong | Yes (brief) |
| `REDIS_PASSWORD` | AWS Secrets Manager + `.env` on EC2 | Medium | Restart Redis + API |
| `GOOGLE_CLIENT_SECRET` | AWS Secrets Manager + Google Cloud Console | High — OAuth breaks if mismatched | Restart API |
| `OPENROUTER_API_KEY` | AWS Secrets Manager + OpenRouter dashboard | High — inference breaks | Restart API |
| `INTERNAL_KEY` | AWS Secrets Manager + `.env` on EC2 | Medium — internal service calls break | Restart API |
| `FLASK_SECRET_KEY` | AWS Secrets Manager + `.env` on EC2 | High — all sessions invalidated | Restart API |
| EC2 SSH Key (RSA) | `.ssh/ec2_private_key.pem` locally + EC2 authorized_keys | High — lose SSH access if done wrong | None (if ED25519 still works) |
| GitHub PAT | GitHub Settings → Developer Settings | High — lose CI/CD if wrong | None |

---

## Rotation Procedures

### 1. DATABASE_URL (PostgreSQL password)

**Rotation steps:**

1. In AWS RDS Console → Databases → `nexusos` → Modify → Set new master password
2. Update AWS Secrets Manager: `/lipaira/DATABASE_URL`
   ```bash
   aws secretsmanager put-secret-value \
     --secret-id /lipaira/DATABASE_URL \
     --secret-string "postgresql://nexusos:<NEW_PASSWORD>@<HOST>:5432/nexusos"
   ```
3. Update `.env` on EC2:
   ```bash
   ssh -i ~/.ssh/ec2_private_key.pem ec2-user@3.147.192.198
   # Edit /home/ec2-user/nexusos/.env — update the DATABASE_URL line
   ```
4. Restart the API and any service that connects to the DB:
   ```bash
   docker exec lipaira-api touch /app/server_full.py
   # Or: docker restart lipaira-api
   ```
5. Verify:
   ```bash
   curl -sf https://api.lipaira.ai/health
   ```

**Rollback:** Revert the password in RDS and restore the previous Secrets Manager value.

---

### 2. REDIS_PASSWORD

**Rotation steps:**

1. Generate new password: `python3 -c "import secrets; print(secrets.token_urlsafe(24))"`
2. Update AWS Secrets Manager: `/lipaira/REDIS_PASSWORD`
3. Update `.env` on EC2: set `REDIS_PASSWORD=<NEW_PASSWORD>`
4. Restart Redis (destroys all in-memory cache and sessions):
   ```bash
   ssh ec2-user@3.147.192.198
   docker stop redis && docker rm redis
   docker run -d \
     --name redis \
     --network nexusos_lipaira-net \
     --restart unless-stopped \
     -v nexusos_redis_data:/data \
     redis:7-alpine \
     redis-server --requirepass <NEW_PASSWORD>
   ```
5. Restart API (reads new password from env):
   ```bash
   docker restart lipaira-api
   ```
6. Verify:
   ```bash
   docker exec redis redis-cli -a <NEW_PASSWORD> ping   # expect PONG
   docker exec redis redis-cli ping                    # expect NOAUTH
   ```

**Note:** REDIS_PASSWORD change invalidates all active sessions.

---

### 3. GOOGLE_CLIENT_SECRET

**Rotation steps:**

1. Go to Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client IDs
2. Select the client → Actions → New secret (or regenerate existing)
3. Update Secrets Manager: `/lipaira/GOOGLE_CLIENT_SECRET`
4. Update `.env` on EC2
5. Restart API
6. Test OAuth flow: initiate a Google OAuth login and confirm it completes

**Important:** If the old secret is still valid in Google's OAuth system, the old secret continues to work until you explicitly revoke it. Revoke the old secret in Google Cloud Console after confirming the new one works.

---

### 4. OPENROUTER_API_KEY

**Rotation steps:**

1. Go to https://openrouter.ai/keys → Generate new key → Copy immediately
2. Update Secrets Manager: `/lipaira/OPENROUTER_API_KEY`
3. Delete the old key from OpenRouter dashboard (prevents accidental use of old key)
4. Update GitHub Actions secret if stored there
5. Restart API if it reads from env
6. Verify:
   ```bash
   curl -s -X POST https://openrouter.ai/api/v1/models \
     -H "Authorization: Bearer <NEW_KEY>" | head -c 100
   ```

---

### 5. INTERNAL_KEY

**Rotation steps:**

1. Generate new key: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Update Secrets Manager: `/lipaira/INTERNAL_KEY`
3. Update `.env` on EC2
4. Restart all services that use `X-Internal-Key` header (API, background tasks):
   ```bash
   docker restart lipaira-api
   ```
5. Verify internal API calls work (e.g., billing sweep, background tasks)

**Warning:** Any service-to-service call using the old `INTERNAL_KEY` will fail with 401 after rotation.

---

### 6. FLASK_SECRET_KEY

**Rotation steps:**

1. Generate new key: `python3 -c "import secrets; print(secrets.token_hex(32))"`
2. Update Secrets Manager: `/lipaira/FLASK_SECRET_KEY`
3. Update `.env` on EC2
4. Restart API:
   ```bash
   docker restart lipaira-api
   ```
5. **All active user sessions are invalidated.** Users must log in again.

---

### 7. EC2 SSH Key (RSA)

**Rotation steps:**

1. Generate new key pair on your local machine:
   ```bash
   ssh-keygen -t rsa -b 4096 -f ~/.ssh/ec2_new_key -N "" -C "lipaira-ec2-$(date +%Y%m%d)"
   ```
2. Add new public key to EC2 authorized_keys:
   ```bash
   cat ~/.ssh/ec2_new_key.pub | ssh -i ~/.ssh/ec2_private_key.pem ec2-user@3.147.192.198 "cat >> ~/.ssh/authorized_keys"
   ```
3. **Test new key works** (keep old key session open):
   ```bash
   ssh -i ~/.ssh/ec2_new_key.pem ec2-user@3.147.192.198 "echo 'new key works'"
   ```
4. Remove old public key from EC2 authorized_keys:
   ```bash
   # Edit ~/.ssh/authorized_keys on EC2 — remove the old key line
   ```
5. Replace old private key locally (update any scripts/automations)

**Warning:** If you lose the new private key and don't have a backup, you lose SSH access to EC2. Keep the new private key safe.

---

## Emergency: Credential Leaked in Git History

If a credential is committed to GitHub:

1. **Rotate the credential immediately** (procedures above)
2. Push a clean commit removing the credential from all branches
3. Use GitHub Secret Scanning to identify all occurrences:  
   Settings → Security → Secret scanning → view alerts
4. Consider using `git filter-repo` to rewrite history (requires force-push to all branches)
5. Notify if the credential had access to PHI (HIPAA breach assessment may be required)

---

## Credential Storage Hierarchy (Correct Order)

For any new credential:

1. **AWS Secrets Manager** — primary store for all secrets (`/lipaira/<CREDENTIAL_NAME>`)
2. **GitHub Actions Secrets** — only for CI/CD (`lipaira` repo → Settings → Secrets → Actions)
3. **`.env` on EC2** — runtime use (read from by services, backed by Secrets Manager)
4. **Never in code** — zero exceptions

Never store credentials in:
- Code comments or docstrings
- Git history (even on private repos)
- Slack, email, or Notion
- Local plaintext files outside of `.ssh/` or `.env/`
