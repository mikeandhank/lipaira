# Login & Verification Spec
*Generated: April 2, 2026*

---

## Current State

| Feature | Status |
|---------|--------|
| Signup UI | ✅ Built |
| Register API | ✅ Built |
| Login UI | ❌ Missing |
| Login API | ✅ Built |
| Phone # on signup | ❌ Missing |
| Email verification | ❌ Missing |
| Phone verification | ❌ Missing |

---

## Login Flow

### Option A: Single Page (Login/Signup toggle)
- One page with two modes: "Sign In" / "Sign Up"
- Toggle between modes
- Shared styling

### Option B: Separate Pages
- `/login` - Login page
- `/signup` - Signup page

**Recommendation:** Option B - clearer UX, easier to track analytics

---

## Signup Flow (Updated)

```
┌─────────────────┐
│   Signup Page   │
│  email          │
│  phone          │
│  password       │
│  [Create Account]────┐
└───────────────────    │
                        ▼
              ┌─────────────────┐
              │  Send Email     │
              │  Verification   │
              │  (6-digit code) │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Verify Page    │
              │  [Enter code]   │
              └────────┬────────┘
                       │ correct
                       ▼
              ┌─────────────────┐
              │  Optional:      │
              │  Phone Verify   │
              │  (SMS code)     │
              └────────┬────────┘
                       │ (skip allowed)
                       ▼
              ┌─────────────────┐
              │  Email: verified│
              │  Phone: opt-in  │
              │  → Onboarding   │
              └─────────────────┘
```

---

## Database Changes

### Add to `users` table:
```sql
-- Phone number (required for verification)
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);

-- Verification status
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT false;

-- Verification codes (temporary)
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_code VARCHAR(6);
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_expires TIMESTAMP;

-- Account status
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;
ALTER TABLE users ADD COLUMN IF NOT EXISTS login_method VARCHAR(20) DEFAULT 'password';  -- password, google, microsoft

-- Unique constraint on phone (when not null)
ALTER TABLE users ADD UNIQUE (phone) WHERE phone IS NOT NULL;
```

### Verification codes table (cleaner approach):
```sql
CREATE TABLE verification_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    code VARCHAR(6) NOT NULL,
    type VARCHAR(20) NOT NULL,  -- email, phone
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_verification_codes_user ON verification_codes(user_id, type);
```

---

## API Endpoints

### POST /api/auth/register-updated
**Request:**
```json
{
  "email": "user@example.com",
  "phone": "+1234567890",  // required
  "password": "securepassword123"
}
```

**Response (success):**
```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "verification_required": true,
  "next_step": "/verify-email"
}
```

**Response (error):**
```json
{
  "error": "Email already registered"
}
```

**Validations:**
- Email: required, valid format, unique
- Phone: required, valid format, valid format (E.164), unique if provided
- Password: min 8 chars, complexity requirements

---

### POST /api/auth/verify-email
**Request:**
```json
{
  "user_id": "uuid",
  "code": "123456"
}
```

**Response (success):**
```json
{
  "verified": true,
  "next_step": "/onboarding"  // or phone verification if optional
}
```

**Response (error):**
```json
{
  "error": "Invalid or expired code"
}
```

---

### POST /api/auth/resend-code
**Request:**
```json
{
  "user_id": "uuid",
  "type": "email"  // or "phone"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Code resent"
}
```

**Rate limit:** 3 requests per hour per user

---

### POST /api/auth/login
**Updated to support unverified:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response (verified):**
```json
{
  "user_id": "uuid",
  "api_key": "lp-xxx",
  "email_verified": true,
  "redirect": "/dashboard"
}
```

**Response (unverified):**
```json
{
  "user_id": "uuid",
  "email_verified": false,
  "redirect": "/verify-email",
  "message": "Please verify your email"
}
```

---

## UI Pages

### 1. Login Page (`/login`)
```
┌─────────────────────────────────────┐
│           lipaira.ai               │
│                                     │
│         Welcome back               │
│                                     │
│  Email or username                 │
│  [________________________]        │
│                                     │
│  Password                          │
│  [________________________]        │
│                                     │
│  [    Sign In    ]                 │
│                                     │
│  Forgot password?                  │
│                                     │
│  ──────── or ────────              │
│                                     │
│  [  Sign in with Google  ]         │
│                                     │
│  Don't have an account? Sign up    │
└─────────────────────────────────────┘
```

### 2. Signup Page (`/signup`) - Updated
```
┌─────────────────────────────────────┐
│           lipaira.ai               │
│                                     │
│         Create account             │
│                                     │
│  Email *                           │
│  [________________________]        │
│                                     │
│  Phone number                      │
│  [________________________]        │
│  (required for verification)  │
│                                     │
│  Password *                        │
│  [________________________]        │
│  Must be 8+ characters             │
│                                     │
│  [    Create Account   ]           │
│                                     │
│  By signing up, you agree to       │
│  Terms of Service and Privacy      │
│                                     │
│  ──────── or ────────              │
│                                     │
│  [  Sign up with Google  ]         │
│                                     │
│  Already have an account? Sign in  │
└─────────────────────────────────────┘
```

### 3. Email Verification (`/verify-email`)
```
┌─────────────────────────────────────┐
│           lipaira.ai               │
│                                     │
│     Verify your email              │
│                                     │
│  We sent a code to                 │
│  user@example.com                  │
│                                     │
│  [1] [2] [3] [4] [5] [6]           │
│  (6-digit code)                    │
│                                     │
│  [    Verify    ]                  │
│                                     │
│  Didn't receive?                   │
│  [Resend code] (0:30)              │
│                                     │
│  Wrong email? [Change it]          │
└─────────────────────────────────────┘
```

---

## Code Generation

### Email verification:
- 6-digit numeric code
- Expires in 10 minutes
- Rate limit: 3 resends per hour
- Store hashed in DB (or in verification_codes table)

### Phone verification:
- 6-digit numeric code  
- Expires in 5 minutes
- Rate limit: 3 resends per hour
- Send via: Resend (SMS) or Twilio

**Note:** Twilio/Resend SMS costs ~$0.01-0.08 per SMS. For MVP, could skip phone verification and just collect phone for account recovery.

---

## Implementation Priority

1. **P0 - Critical:**
   - Add phone column to users table
   - Add email_verified column + default false
   - Update register endpoint to require verification
   - Add email verification code generation + sending
   - Add verify-email endpoint

2. **P1 - Important:**
   - Create Login page UI
   - Update Login endpoint to check verified status
   - Update signup flow to show verification step

3. **P2 - Nice to have:**
   - Phone verification (SMS)
   - Password reset flow
   - Social login (Google already exists)

---

## File Changes Required

### Backend:
- `server_full.py` - Update register, login, add verify endpoints
- `db.py` - Add migration for phone + verification columns

### Frontend:
- `lipaira-web/src/pages/Login.jsx` - NEW
- `lipaira-web/src/pages/Signup.jsx` - Update (add phone)
- `lipaira-web/src/pages/VerifyEmail.jsx` - NEW
- `lipaira-web/src/App.jsx` - Add routes

### Email:
- Update Resend email template for verification code