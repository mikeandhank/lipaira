#!/bin/bash
# NexusOS v6 Deploy Script
# Run this in the server console

set -e

echo "=== NexusOS v6 Deploy ==="

# Stop current container
echo "Stopping current container..."
docker rm -f nexusos-v6 || true

# If you need to transfer the file from local machine, run this on YOUR LOCAL terminal:
# scp /path/to/nexusos-v6-deploy.tar.gz admin@187.124.150.225:/root/

# Or if the file is already on the server:
echo "Extracting..."
cd /root
tar -xzf nexusos-v6-deploy.tar.gz

# Rebuild and start
echo "Building Docker image..."
cd nexusos-v2
docker build -t nexusos-v6 .

echo "Starting container..."
docker run -d \
  --name nexusos-v6 \
  -p 8080:8080 \
  -e NEXUSOS_SECRET=$(openssl rand -hex 32) \
  -e DATABASE_URL="$DATABASE_URL" \
  -e REDIS_URL="$REDIS_URL" \
  -v nexusos-data:/opt/nexusos-data \
  nexusos-v6

echo "Done! API should be at http://localhost:8080"
docker logs -f nexusos-v6
