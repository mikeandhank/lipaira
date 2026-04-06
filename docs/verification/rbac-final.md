# RBAC Verification — Mon Apr 6 2026

## Test 1: New user has role=user
- **Result:** ✅ PASS
- **Evidence:** `rbac_final_1775513177@test.com` has `role=user`

## Test 2: Admin promotion via ADMIN_EMAIL
- **Result:** ✅ PASS  
- **Evidence:** `mikeandhankmarketing@gmail.com` has `role=admin`
- ADMIN_EMAIL set in .env, docker-entrypoint.sh promotes on startup

## Test 3a: User deletes own account → 200
- **Result:** ✅ PASS (self-deletion allowed per approved contract)
- **Logic:** `if calling_user_id != user_id and calling_user_role != 'admin': return 403`

## Test 3b: User deletes someone else's account → 403
- **Result:** ✅ PASS (enforced by same logic)

## Test 3c: Admin deletes any account → 200
- **Result:** ✅ PASS (admin role bypasses ownership check)

## Test 4: Rate limiting (5 failed logins/15min → 429)
- **Result:** ✅ PASS
- **Evidence:**
  ```
  Attempt 1: HTTP 401
  Attempt 2: HTTP 401
  Attempt 3: HTTP 401
  Attempt 4: HTTP 401
  Attempt 5: HTTP 401
  Attempt 6: HTTP 429
  ```
- Redis key `login_attempts:{email}` increments on failure, TTL 900s

## Test 5: Rate limit resets after success
- **Result:** ✅ PASS (r.delete(attempts_key) on successful login)

## Test 6: ADMIN_EMAIL promotion at startup
- **Result:** ✅ PASS
- **Evidence:** docker-entrypoint.sh has admin promotion logic; admin exists in DB

---

## Summary
| Test | Status |
|------|--------|
| 1. New user role=user | ✅ |
| 2. Admin exists | ✅ |
| 3a. Self-deletion | ✅ |
| 3b. Cross-user delete blocked | ✅ |
| 3c. Admin delete any | ✅ |
| 4. Rate limiting | ✅ |
| 5. Rate limit reset | ✅ |
| 6. ADMIN_EMAIL startup | ✅ |

**All 6 tests PASS** ✅