#!/bin/bash
# docker-entrypoint.sh
# Runs core DB migrations before starting the API server.
# Migrations must pass before gunicorn starts — fail-fast.

set -e

echo "[entrypoint] Starting Lipaira API..."

# Wait for postgres to be ready
if [ -n "$DATABASE_URL" ]; then
    echo "[entrypoint] Waiting for postgres..."
    # Extract host from DATABASE_URL
    DB_HOST=$(echo "$DATABASE_URL" | sed -E 's|.*@([^:/]+).*|\1|')
    DB_NAME=$(echo "$DATABASE_URL" | sed -E 's|.*/(.*)|\1|' | sed 's/?.*//')
    
    until PGPASSWORD=$(echo "$DATABASE_URL" | sed -E 's|.*:(.+)@.*|\1|') \
        psql -h "$DB_HOST" -U "$(echo "$DATABASE_URL" | sed -E 's|.*://([^:]+):.*|\1|')" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; do
        echo "[entrypoint] Postgres not ready — waiting..."
        sleep 2
    done
    echo "[entrypoint] Postgres is ready."
fi

# Run migrations (skip if SKIP_MIGRATIONS=1)
MIGRATIONS_DIR="/opt/lipaira/app/migrations"
if [ "$SKIP_MIGRATIONS" = "1" ]; then
    echo "[entrypoint] SKIP_MIGRATIONS=1 — skipping migrations"
elif [ -d "$MIGRATIONS_DIR" ]; then
    echo "[entrypoint] Running migrations..."

    # Enable pgcrypto extension first
    if [ -n "$DATABASE_URL" ]; then
        PGPASSWORD=$(echo "$DATABASE_URL" | sed -E 's|.*:(.+)@.*|\1|') \
        psql -h "$DB_HOST" -U "$(echo "$DATABASE_URL" | sed -E 's|.*://([^:]+):.*|\1|')" -d "$DB_NAME" \
            -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;" 2>/dev/null || true
    fi

    # Run migration files in order
    for f in $(ls "$MIGRATIONS_DIR"/*.sql 2>/dev/null | sort); do
        echo "[entrypoint] Applying: $(basename $f)"
        if [ -n "$DATABASE_URL" ]; then
            PGPASSWORD=$(echo "$DATABASE_URL" | sed -E 's|.*:(.+)@.*|\1|') \
            psql -h "$DB_HOST" -U "$(echo "$DATABASE_URL" | sed -E 's|.*://([^:]+):.*|\1|')" -d "$DB_NAME" \
                -f "$f" || {
                echo "[entrypoint] WARNING: Migration $(basename $f) had errors (continuing)"
            }
        else
            echo "[entrypoint] WARNING: DATABASE_URL not set — skipping migration $f"
        fi
    done
    echo "[entrypoint] Migrations complete."
else
    echo "[entrypoint] No migrations directory found at $MIGRATIONS_DIR — skipping."
fi

# Admin promotion: if ADMIN_EMAIL is set, promote that user to admin (idempotent)
if [ -n "$ADMIN_EMAIL" ] && [ -n "$DATABASE_URL" ]; then
    echo "[entrypoint] Checking for admin promotion: $ADMIN_EMAIL"
    PGPASSWORD=$(echo "$DATABASE_URL" | sed -E 's|.*:(.+)@.*|\1|') \
    psql -h "$DB_HOST" -U "$(echo "$DATABASE_URL" | sed -E 's|.*://([^:]+):.*|\1|')" -d "$DB_NAME" \
        -c "UPDATE users SET role='admin' WHERE email='$ADMIN_EMAIL';" 2>/dev/null || true
    echo "[entrypoint] Admin promotion complete."
fi

echo "[entrypoint] Starting gunicorn..."
exec "$@"

# Load VAPID keys from AWS Secrets Manager if not already set
if [ -z "$VAPID_PRIVATE_KEY" ] || [ -z "$VAPID_PUBLIC_KEY" ]; then
    if command -v aws &> /dev/null; then
        echo "[entrypoint] Loading VAPID keys from ASM..."
        VAPID_PRIVATE_KEY=$(aws secretsmanager get-secret-value --secret-id /lipaira/vapid-private-key --region us-east-1 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['SecretString'])" 2>/dev/null || echo "")
        VAPID_PUBLIC_KEY=$(aws secretsmanager get-secret-value --secret-id /lipaira/vapid-public-key --region us-east-1 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['SecretString'])" 2>/dev/null || echo "")
        VAPID_SUBJECT=$(aws secretsmanager get-secret-value --secret-id /lipaira/vapid-subject --region us-east-1 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['SecretString'])" 2>/dev/null || echo "mailto:admin@lipaira.ai")
        export VAPID_PRIVATE_KEY VAPID_PUBLIC_KEY VAPID_SUBJECT
        echo "[entrypoint] VAPID keys loaded."
    fi
fi
