# feel free to ignore this comment
     1|#!/bin/bash
     2|# docker-entrypoint.sh
     3|# Runs core DB migrations before starting the API server.
     4|# Migrations must pass before gunicorn starts — fail-fast.
     5|
     6|set -e
     7|
     8|echo "[entrypoint] Starting Lipaira API..."
     9|
    10|# Wait for postgres to be ready
    11|if [ -n "$DATABASE_URL" ]; then
    12|    echo "[entrypoint] Waiting for postgres..."
    13|    # Extract host from DATABASE_URL
    14|    DB_HOST=$(echo "$DATABASE_URL" | sed -E 's|.*@([^:/]+).*|\1|')
    15|    DB_NAME=$(echo "$DATABASE_URL" | sed -E 's|.*/(.*)|\1|' | sed 's/?.*//')
    16|    
    17|    until PGPASSWORD=*** "$DATABASE_URL" | sed -E 's|.*:(.+)@.*|\1|') \
    18|        psql -h "$DB_HOST" -U "$(echo "$DATABASE_URL" | sed -E 's|.*://([^:]+):.*|\1|')" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; do
    19|        echo "[entrypoint] Postgres not ready — waiting..."
    20|        sleep 2
    21|    done
    22|    echo "[entrypoint] Postgres is ready."
    23|fi
    24|
    25|# Run migrations (skip if SKIP_MIGRATIONS=1)
    26|MIGRATIONS_DIR="/opt/lipaira/app/migrations"
    27|if [ "$SKIP_MIGRATIONS" = "1" ]; then
    28|    echo "[entrypoint] SKIP_MIGRATIONS=1 — skipping migrations"
    29|elif [ -d "$MIGRATIONS_DIR" ]; then
    30|    echo "[entrypoint] Running migrations..."
    31|
    32|    # Enable pgcrypto extension first
    33|    if [ -n "$DATABASE_URL" ]; then
    34|        PGPASSWORD=*** "$DATABASE_URL" | sed -E 's|.*:(.+)@.*|\1|') \
    35|        psql -h "$DB_HOST" -U "$(echo "$DATABASE_URL" | sed -E 's|.*://([^:]+):.*|\1|')" -d "$DB_NAME" \
    36|            -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;" 2>/dev/null || true
    37|    fi
    38|
    39|    # Run migration files in order
    40|    for f in $(ls "$MIGRATIONS_DIR"/*.sql 2>/dev/null | sort); do
    41|        echo "[entrypoint] Applying: $(basename $f)"
    42|        if [ -n "$DATABASE_URL" ]; then
    43|            PGPASSWORD=*** "$DATABASE_URL" | sed -E 's|.*:(.+)@.*|\1|') \
    44|            psql -h "$DB_HOST" -U "$(echo "$DATABASE_URL" | sed -E 's|.*://([^:]+):.*|\1|')" -d "$DB_NAME" \
    45|                -f "$f" || {
    46|                echo "[entrypoint] WARNING: Migration $(basename $f) had errors (continuing)"
    47|            }
    48|        else
    49|            echo "[entrypoint] WARNING: DATABASE_URL not set — skipping migration $f"
    50|        fi
    51|    done
    52|    echo "[entrypoint] Migrations complete."
    53|else
    54|    echo "[entrypoint] No migrations directory found at $MIGRATIONS_DIR — skipping."
    55|fi
    56|
    57|# Admin promotion: if ADMIN_EMAIL is set, promote that user to admin (idempotent)
    58|if [ -n "$ADMIN_EMAIL" ] && [ -n "$DATABASE_URL" ]; then
    59|    echo "[entrypoint] Checking for admin promotion: $ADMIN_EMAIL"
    60|    PGPASSWORD=*** "$DATABASE_URL" | sed -E 's|.*:(.+)@.*|\1|') \
    61|    psql -h "$DB_HOST" -U "$(echo "$DATABASE_URL" | sed -E 's|.*://([^:]+):.*|\1|')" -d "$DB_NAME" \
    62|        -c "UPDATE users SET role='admin' WHERE email='$ADMIN_EMAIL';" 2>/dev/null || true
    63|    echo "[entrypoint] Admin promotion complete."
    64|fi
    65|
    66|echo "[entrypoint] Starting gunicorn..."
    67|exec "$@"
    68|
    69|# Load VAPID keys from AWS Secrets Manager if not already set
    70|if [ -z "$VAPID_PRIVATE_KEY" ] || [ -z "$VAPID_PUBLIC_KEY" ]; then
    71|    if command -v aws &> /dev/null; then
    72|        echo "[entrypoint] Loading VAPID keys from ASM..."
    73|        VAPID_PRIVATE_KEY=$(aws secretsmanager get-secret-value --secret-id /lipaira/vapid-private-key --region us-east-1 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['SecretString'])" 2>/dev/null || echo "")
    74|        VAPID_PUBLIC_KEY=$(aws secretsmanager get-secret-value --secret-id /lipaira/vapid-public-key --region us-east-1 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['SecretString'])" 2>/dev/null || echo "")
    75|        VAPID_SUBJECT=$(aws secretsmanager get-secret-value --secret-id /lipaira/vapid-subject --region us-east-1 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['SecretString'])" 2>/dev/null || echo "mailto:admin@lipaira.ai")
    76|        export VAPID_PRIVATE_KEY VAPID_PUBLIC_KEY VAPID_SUBJECT
    77|        echo "[entrypoint] VAPID keys loaded."
    78|    fi
    79|fi
    80|
    81|# Load VAPID keys from AWS Secrets Manager using boto3
    82|if [ -z "$VAPID_PRIVATE_KEY" ] || [ -z "$VAPID_PUBLIC_KEY" ]; then
    83|    echo "[entrypoint] Loading VAPID keys from ASM via boto3..."
    84|    VAPID_PRIVATE_KEY=$(python3 -c "
    85|import boto3, json, os
    86|try:
    87|    client = boto3.client('secretsmanager', region_name='us-east-1')
    88|    resp = client.get_secret_value(SecretId='/lipaira/vapid-private-key')
    89|    print(resp['SecretString'])
    90|except: pass
    91|" 2>/dev/null)
    92|    
    93|    VAPID_PUBLIC_KEY=$(python3 -c "
    94|import boto3, json, os
    95|try:
    96|    client = boto3.client('secretsmanager', region_name='us-east-1')
    97|    resp = client.get_secret_value(SecretId='/lipaira/vapid-public-key')
    98|    print(resp['SecretString'])
    99|except: pass
   100|" 2>/dev/null)
   101|    
   102|    VAPID_SUBJECT=$(python3 -c "
   103|import boto3, json, os
   104|try:
   105|    client = boto3.client('secretsmanager', region_name='us-east-1')
   106|    resp = client.get_secret_value(SecretId='/lipaira/vapid-subject')
   107|    print(resp['SecretString'])
   108|except: print('mailto:admin@lipaira.ai')
   109|" 2>/dev/null)
   110|    
   111|    if [ -n "$VAPID_PRIVATE_KEY" ]; then
   112|        export VAPID_PRIVATE_KEY VAPID_PUBLIC_KEY VAPID_SUBJECT
   113|        echo "[entrypoint] VAPID keys loaded successfully."
   114|    else
   115|        echo "[entrypoint] VAPID keys not found in ASM."
   116|    fi
   117|fi
   118|