#!/bin/bash
#
# Lipaira OS Installer
# ====================
# One-command install: curl -sSL https://lipaira.ai/install | bash
#
# Supports:
#   - Docker-based deployment (recommended)
#   - All billing through Lipaira cloud
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Config
LIPAIRA_VERSION="0.1.0"
LIPAIRA_DIR="/opt/lipaira"
LIPAIRA_CONFIG_DIR="/etc/lipaira"
INSTALL_LOG="/var/log/lipaira-install.log"

# Logging
log() { echo -e "${GREEN}[LIPAIRA]${NC} $1"; }
warn() { echo -e "${YELLOW}[LIPAIRA]${NC} $1"; }
error() { echo -e "${RED}[LIPAIRA]${NC} $1"; }
info() { echo -e "${BLUE}[LIPAIRA]${NC} $1"; }

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Check prerequisites
check_prereqs() {
    log "Checking prerequisites..."
    
    # Check for Docker
    if ! command -v docker &> /dev/null; then
        warn "Docker not found. Installing Docker..."
        install_docker
    fi
    
    # Check for Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        warn "Docker Compose not found. Installing..."
        install_docker_compose
    fi
    
    # Check ports
    check_ports
    
    log "Prerequisites OK"
}

install_docker() {
    info "Installing Docker..."
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sh /tmp/get-docker.sh
    systemctl enable docker
    systemctl start docker
    log "Docker installed"
}

install_docker_compose() {
    # Docker Compose v2 is included in Docker
    # Check if we have `docker compose` (v2) or `docker-compose` (v1)
    if docker compose version &> /dev/null; then
        log "Docker Compose v2 available"
    else
        warn "Using docker-compose v1"
    fi
}

check_ports() {
    info "Checking available ports..."
    
    # Check ports we need
    for port in 80 443 8080; do
        if netstat -tuln 2>/dev/null | grep -q ":$port " || ss -tuln 2>/dev/null | grep -q ":$port "; then
            warn "Port $port is in use"
        else
            log "Port $port available"
        fi
    done
}

# Create directories
create_dirs() {
    log "Creating directories..."
    mkdir -p "$LIPAIRA_DIR"
    mkdir -p "$LIPAIRA_CONFIG_DIR"
    mkdir -p "$LIPAIRA_DIR/data"
    mkdir -p "$LIPAIRA_DIR/logs"
    mkdir -p "$LIPAIRA_DIR/plugins"
}

# Download Docker Compose file
download_compose() {
    log "Downloading Lipaira OS..."
    
    cat > "$LIPAIRA_DIR/docker-compose.yml" << 'EOF'
version: '3.8'

services:
  lipaira-server:
    image: lipaira/server:${LIPAIRA_VERSION:-latest}
    container_name: lipaira-server
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data
      - ./config:/config
      - ./logs:/logs
    environment:
      - LIPAIRA_MODE=self-hosted
      - LIPAIRA_SECRET_KEY=${LIPAIRA_SECRET_KEY}
      - LIPAIRA_DB_HOST=postgres
      - LIPAIRA_DB_USER=lipaira
      - LIPAIRA_DB_PASSWORD=${LIPAIRA_DB_PASSWORD}
      - LIPAIRA_DB_NAME=lipaira
      - LIPAIRA_REDIS_HOST=redis
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:16-alpine
    container_name: lipaira-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: lipaira
      POSTGRES_PASSWORD: ${LIPAIRA_DB_PASSWORD}
      POSTGRES_DB: lipaira
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    container_name: lipaira-redis
    restart: unless-stopped
    volumes:
      - redis_data:/data

  lipaira-ui:
    image: lipaira/webapp:${LIPAIRA_VERSION:-latest}
    container_name: lipaira-webapp
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - lipaira-server

volumes:
  postgres_data:
  redis_data:
EOF

    log "Docker Compose file created"
}

# Generate config
generate_config() {
    log "Generating configuration..."
    
    # Generate secret key
    SECRET_KEY=$(openssl rand -hex 32)
    DB_PASSWORD=$(openssl rand -hex 16)
    
    cat > "$LIPAIRA_CONFIG_DIR/env" << EOF
# Lipaira OS Configuration
# Generated: $(date)

# Mode: self-hosted or cloud
LIPAIRA_MODE=self-hosted

# Server Configuration
LIPAIRA_SECRET_KEY=$SECRET_KEY
LIPAIRA_HOST=0.0.0.0
LIPAIRA_PORT=8080

# Database
LIPAIRA_DB_HOST=postgres
LIPAIRA_DB_PORT=5432
LIPAIRA_DB_USER=lipaira
LIPAIRA_DB_PASSWORD=$DB_PASSWORD
LIPAIRA_DB_NAME=lipaira

# Redis
LIPAIRA_REDIS_HOST=redis
LIPAIRA_REDIS_PORT=6379

# ==============================================
# BILLING
# ==============================================
# All billing is handled by Lipaira (us).
# Users buy credits from us through our server.
# 
# Self-hosted mode means user runs the OS on their VPS,
# but it connects to our server for billing + LLM routing.
# ==============================================

# Connection to Lipaira cloud (REQUIRED for billing)
LIPAIRA_API_URL=https://api.lipaira.ai
LIPAIRA_API_KEY=xxx  # Get from lipaira.ai dashboard

# Security
LIPAIRA_SANDBOX_ENABLED=true
LIPAIRA_ALLOW_NETWORK=false

# Logging
LIPAIRA_LOG_LEVEL=info
EOF

    # Copy to data dir
    cp "$LIPAIRA_CONFIG_DIR/env" "$LIPAIRA_DIR/.env"
    
    log "Configuration generated at $LIPAIRA_CONFIG_DIR/env"
}

# Pull images
pull_images() {
    log "Pulling Docker images (this may take a few minutes)..."
    
    cd "$LIPAIRA_DIR"
    
    # For now, we'll build from local code if available
    # In production, we'd have a registry
    if [ -d "/data/.openclaw/workspace/nexusos" ]; then
        warn "Building from local source..."
        # Build locally for now
    else
        info "To deploy: get API key from https://lipaira.ai"
    fi
}

# Setup systemd service
setup_service() {
    log "Setting up systemd service..."
    
    cat > /etc/systemd/system/lipaira.service << 'EOF'
[Unit]
Description=Lipaira AI Agent OS
After=network.target docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/lipaira
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable lipaira.service
    
    log "System service installed"
}

# Create CLI tool
create_cli() {
    log "Installing Lipaira CLI..."
    
    cat > /usr/local/bin/lipaira << 'EOF'
#!/bin/bash

LIPAIRA_DIR="/opt/lipaira"

case "$1" in
    start)
        cd "$LIPAIRA_DIR" && docker compose up -d
        ;;
    stop)
        cd "$LIPAIRA_DIR" && docker compose down
        ;;
    restart)
        cd "$LIPAIRA_DIR" && docker compose restart
        ;;
    status)
        cd "$LIPAIRA_DIR" && docker compose ps
        ;;
    logs)
        docker compose logs -f "${2:-}"
        ;;
    config)
        nano "$LIPAIRA_CONFIG_DIR/env"
        ;;
    update)
        cd "$LIPAIRA_DIR" && docker compose pull && docker compose up -d
        ;;
    *)
        echo "Lipaira OS CLI"
        echo ""
        echo "Usage: lipaira <command>"
        echo ""
        echo "Commands:"
        echo "  start     - Start Lipaira OS"
        echo "  stop      - Stop Lipaira OS"
        echo "  restart   - Restart Lipaira OS"
        echo "  status    - Show status"
        echo "  logs      - View logs"
        echo "  config    - Edit configuration"
        echo "  update    - Update to latest version"
        ;;
esac
EOF

    chmod +x /usr/local/bin/lipaira
    log "CLI installed: lipaira start|stop|restart|status|logs|config|update"
}

# Print next steps
print_next_steps() {
    echo ""
    echo "========================================"
    echo -e "${GREEN}Installation Complete!${NC}"
    echo "========================================"
    echo ""
    echo "Next steps:"
    echo ""
    echo "1. Get API key:"
    echo "   Sign up at https://lipaira.ai and get your API key"
    echo "   Edit /etc/lipaira/env and add LIPAIRA_API_KEY=xxx"
    echo ""
    echo "2. Start Lipaira OS:"
    echo "   sudo lipaira start"
    echo ""
    echo "3. Check status:"
    echo "   sudo lipaira status"
    echo ""
    echo "4. View logs:"
    echo "   sudo lipaira logs"
    echo ""
    echo "========================================"
    echo ""
    info "Access the web UI at: http://$(hostname -I | awk '{print $1}')"
    echo ""
}

# Main
main() {
    log "Lipaira OS Installer v$LIPAIRA_VERSION"
    log "========================================"
    
    check_root
    check_prereqs
    create_dirs
    download_compose
    generate_config
    create_cli
    setup_service
    
    print_next_steps
}

main "$@"