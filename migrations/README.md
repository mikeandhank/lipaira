# Migrations

## Active Migrations

| File | Purpose | Notes |
|------|---------|-------|
| `001_core_schema.sql` | All core tables (users, billing, memory, integrations, etc.) | Run first. Idempotent. |
| `businesses/` | Multi-business support | Run after 001_core_schema.sql |
| `integrations/` | Integration-specific tables (DNS, website) | Run after 001_core_schema.sql |

## Superseded

Files in `superseded/` have been consolidated into `001_core_schema.sql`. Do not run them.

## Running Migrations

The docker-entrypoint handles this automatically on container start.

To run manually:
```bash
psql $DATABASE_URL -f migrations/001_core_schema.sql
psql $DATABASE_URL -f migrations/businesses/001_create_businesses.sql
psql $DATABASE_URL -f migrations/integrations/001_extend_user_integrations.sql
```

## Migration Order

001_core_schema.sql must run first. All others run after.
