FROM alpine:3.19 AS base

# Install base dependencies
RUN apk add --no-cache \
    bash \
    curl \
    wget \
    git \
    sqlite \
    python3 \
    py3-pip \
    nodejs \
    npm \
    nginx \
    tini

# Create nexus user
RUN adduser -D -s /bin/bash nexus && \
    mkdir -p /home/nexus && \
    chown -R nexus:nexus /home/nexus

WORKDIR /home/nexus

# ============ STAGE 1: Dependencies ============
FROM base AS deps

# Install Python packages
RUN pip3 install --no-cache-dir --break-system-packages \
    aiohttp \
    pydantic \
    python-dotenv \
    sqlalchemy \
    pytest \
    pytest-asyncio

# Install Node.js packages globally
RUN npm install -g pnpm

# ============ STAGE 2: NexusOS Core ============
FROM base AS nexus

# Create directory structure
RUN mkdir -p /nexus/{config,memory/{episodic,semantic,working},tools,logs,sandbox,state}

# Copy provisioning scripts
COPY --from=deps /usr/bin/python3 /usr/bin/
COPY --from=deps /usr/local/bin/pnpm /usr/local/bin/

# Copy Python packages
RUN apk add --no-cache python3 py3-pip

# Install Python deps
RUN pip3 install --no-cache-dir --break-system-packages \
    aiohttp \
    pydantic \
    python-dotenv \
    sqlalchemy \
    uvicorn \
    fastapi

# Copy NexusOS tools
COPY tools/ /nexus/tools/
RUN chmod +x /nexus/tools/*/server.py /nexus/tools/*/server.js 2>/dev/null || true

# Copy config
COPY config/ /nexus/config/

# Set ownership
RUN chown -R nexus:nexus /nexus

# Environment
ENV NEXUS_HOME=/nexus
ENV NEXUS_MEMORY=/nexus/memory
ENV NEXUS_CONFIG=/nexus/config

USER nexus

# ============ STAGE 3: Runtime ============
FROM nexus AS runtime

# Expose ports
# Memory server: 4893
# Filesystem MCP: 4894
# Process MCP: 4895
# HTTP MCP: 4896
# OpenClaw: 8080 (default)
EXPOSE 4893 4894 4895 4896 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost:4893/health || exit 1

# Entry point
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]