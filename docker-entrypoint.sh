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

# Run migrations
MIGRATIONS_DIR="/opt/lipaira/app/migrations"
if [ -d "$MIGRATIONS_DIR" ]; then
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
                echo "[entrypoint] MIGRATION FAILED: $(basename $f)"
                exit 1
            }
        else
            echo "[entrypoint] WARNING: DATABASE_URL not set — skipping migration $f"
        fi
    done
    echo "[entrypoint] Migrations complete."
else
    echo "[entrypoint] No migrations directory found at $MIGRATIONS_DIR — skipping."
fi

echo "[entrypoint] Starting gunicorn..."
exec "$@"
