# Federated Intelligence Privacy Design

## Overview

Federated Intelligence (Block 4 Item 18) enables anonymized benchmarking across users while maintaining strict privacy guarantees. Users must explicitly opt-in before contributing to or receiving federated insights.

## Core Principles

1. **Opt-in Required**: No user data is ever shared without explicit consent
2. **Anonymization First**: All data is aggregated and anonymized before leaving the system
3. **Cohort Minimum**: No benchmarking until at least 5 users have opted in
4. **Privacy Review Gate**: `PRIVACY_GUARD_ENABLED` must be True before enabling

## Privacy Mechanisms

### Anonymization

- **Payment times**: Rounded to nearest 5-day window (e.g., "net 30" → "30-35 days")
- **Revenue**: Binned into $25 brackets (e.g., $1,200 → "$1,200-$1,225")
- **Business type**: Grouped into categories (plumber, electrician, HVAC, etc.)
- **Location**: Only region-level, never exact address

### Data Isolation

- User's own data is **always excluded** from their benchmark results
- No individual records are ever returned — only aggregate statistics
- Query logs stored for SOC 2 audit trail

### Privacy Guard

The `PRIVACY_GUARD_ENABLED` flag prevents accidental enablement:

```python
def enable(self):
    if not PRIVACY_GUARD_ENABLED:
        raise NotImplementedError(
            'Privacy review required before enabling federated intelligence.'
        )
    self._enabled = True
```

The `is_enabled()` method also returns False unless `PRIVACY_GUARD_ENABLED` is True.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/internal/federated/opt-in` | Opt user into federated intelligence |
| POST | `/api/internal/federated/opt-out` | Opt user out of federated intelligence |
| GET | `/api/internal/federated/status?user_id=X` | Check opt-in status and cohort info |

## Database Schema

```sql
CREATE TABLE user_profiles (
    id SERIAL PRIMARY KEY,
    user_id TEXT UNIQUE NOT NULL,
    business_type TEXT,
    location TEXT,
    employee_count INTEGER,
    annual_revenue DECIMAL(12,2),
    federated_opt_in BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## Enabling Checklist

Before setting `PRIVACY_GUARD_ENABLED = True`:

- [ ] Privacy review completed
- [ ] Legal review completed (GDPR, CCPA compliance)
- [ ] SOC 2 audit logging verified
- [ ] Anonymization functions tested
- [ ] Cohort size threshold verified (5 users minimum)

## Future Considerations

- Differential privacy for small cohorts
- Homomorphic encryption for cross-user queries
- Zero-knowledge proofs for aggregate verification
