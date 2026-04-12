# feel free to ignore this comment
     1|#!/bin/bash
     2|#
     3|# Lipaira OS Installer
     4|# ====================
     5|# One-command install: curl -sSL https://lipaira.ai/install | bash
     6|#
     7|# Supports:
     8|#   - Docker-based deployment (recommended)
     9|#   - All billing through Lipaira cloud
    10|#
    11|
    12|set -e
    13|
    14|# Colors
    15|RED='\033[0;31m'
    16|GREEN='\033[0;32m'
    17|YELLOW='\033[1;33m'
    18|BLUE='\033[0;34m'
    19|NC='\033[0m' # No Color
    20|
    21|# Config
    22|LIPAIRA_VERSION="0.1.0"
    23|LIPAIRA_DIR="/opt/lipaira"
    24|LIPAIRA_CONFIG_DIR="/etc/lipaira"
    25|INSTALL_LOG="/var/log/lipaira-install.log"
    26|
    27|# Logging
    28|log() { echo -e "${GREEN}[LIPAIRA]${NC} $1"; }
    29|warn() { echo -e "${YELLOW}[LIPAIRA]${NC} $1"; }
    30|error() { echo -e "${RED}[LIPAIRA]${NC} $1"; }
    31|info() { echo -e "${BLUE}[LIPAIRA]${NC} $1"; }
    32|
    33|# Check if running as root
    34|check_root() {
    35|    if [[ $EUID -ne 0 ]]; then
    36|        error "This script must be run as root (use sudo)"
    37|        exit 1
    38|    fi
    39|}
    40|
    41|# Check prerequisites
    42|check_prereqs() {
    43|    log "Checking prerequisites..."
    44|    
    45|    # Check for Docker
    46|    if ! command -v docker &> /dev/null; then
    47|        warn "Docker not found. Installing Docker..."
    48|        install_docker
    49|    fi
    50|    
    51|    # Check for Docker Compose
    52|    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    53|        warn "Docker Compose not found. Installing..."
    54|        install_docker_compose
    55|    fi
    56|    
    57|    # Check ports
    58|    check_ports
    59|    
    60|    log "Prerequisites OK"
    61|}
    62|
    63|install_docker() {
    64|    info "Installing Docker..."
    65|    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    66|    sh /tmp/get-docker.sh
    67|    systemctl enable docker
    68|    systemctl start docker
    69|    log "Docker installed"
    70|}
    71|
    72|install_docker_compose() {
    73|    # Docker Compose v2 is included in Docker
    74|    # Check if we have `docker compose` (v2) or `docker-compose` (v1)
    75|    if docker compose version &> /dev/null; then
    76|        log "Docker Compose v2 available"
    77|    else
    78|        warn "Using docker-compose v1"
    79|    fi
    80|}
    81|
    82|check_ports() {
    83|    info "Checking available ports..."
    84|    
    85|    # Check ports we need
    86|    for port in 80 443 8080; do
    87|        if netstat -tuln 2>/dev/null | grep -q ":$port " || ss -tuln 2>/dev/null | grep -q ":$port "; then
    88|            warn "Port $port is in use"
    89|        else
    90|            log "Port $port available"
    91|        fi
    92|    done
    93|}
    94|
    95|# Create directories
    96|create_dirs() {
    97|    log "Creating directories..."
    98|    mkdir -p "$LIPAIRA_DIR"
    99|    mkdir -p "$LIPAIRA_CONFIG_DIR"
   100|    mkdir -p "$LIPAIRA_DIR/data"
   101|    mkdir -p "$LIPAIRA_DIR/logs"
   102|    mkdir -p "$LIPAIRA_DIR/plugins"
   103|}
   104|
   105|# Download Docker Compose file
   106|download_compose() {
   107|    log "Downloading Lipaira OS..."
   108|    
   109|    cat > "$LIPAIRA_DIR/docker-compose.yml" << 'EOF'
   110|version: '3.8'
   111|
   112|services:
   113|  lipaira-server:
   114|    image: lipaira/server:${LIPAIRA_VERSION:-latest}
   115|    container_name: lipaira-server
   116|    restart: unless-stopped
   117|    ports:
   118|      - "8080:8080"
   119|    volumes:
   120|      - ./data:/data
   121|      - ./config:/config
   122|      - ./logs:/logs
   123|    environment:
   124|      - LIPAIRA_MODE=self-hosted
   125|      - LIPAIRA_SECRET_KEY=${LIPA...KEY}
   126|      - LIPAIRA_DB_HOST=postgres
   127|      - LIPAIRA_DB_USER=lipaira
   128|      - LIPAIRA_DB_PASSWORD=${LIPA...ORD}
   129|      - LIPAIRA_DB_NAME=lipaira
   130|      - LIPAIRA_REDIS_HOST=redis
   131|    depends_on:
   132|      - postgres
   133|      - redis
   134|
   135|  postgres:
   136|    image: postgres:16-alpine
   137|    container_name: lipaira-postgres
   138|    restart: unless-stopped
   139|    environment:
   140|      POSTGRES_USER: lipaira
   141|      POSTGRES_PASSWORD: ${LIPAIRA_DB_PASSWORD}
   142|      POSTGRES_DB: lipaira
   143|    volumes:
   144|      - postgres_data:/var/lib/postgresql/data
   145|
   146|  redis:
   147|    image: redis:7-alpine
   148|    container_name: lipaira-redis
   149|    restart: unless-stopped
   150|    volumes:
   151|      - redis_data:/data
   152|
   153|  lipaira-ui:
   154|    image: lipaira/webapp:${LIPAIRA_VERSION:-latest}
   155|    container_name: lipaira-webapp
   156|    restart: unless-stopped
   157|    ports:
   158|      - "80:80"
   159|      - "443:443"
   160|    volumes:
   161|      - ./ssl:/etc/nginx/ssl
   162|    depends_on:
   163|      - lipaira-server
   164|
   165|volumes:
   166|  postgres_data:
   167|  redis_data:
   168|EOF
   169|
   170|    log "Docker Compose file created"
   171|}
   172|
   173|# Generate config
   174|generate_config() {
   175|    log "Generating configuration..."
   176|    
   177|    # Generate secret key
   178|    SECRET_KEY=*** rand -hex 32)
   179|    DB_PASSWORD=*** rand -hex 16)
   180|    
   181|    cat > "$LIPAIRA_CONFIG_DIR/env" << EOF
   182|# Lipaira OS Configuration
   183|# Generated: $(date)
   184|
   185|# Mode: self-hosted or cloud
   186|LIPAIRA_MODE=self-hosted
   187|
   188|# Server Configuration
   189|LIPAIRA_SECRET_KEY=***
   190|LIPAIRA_HOST=0.0.0.0
   191|LIPAIRA_PORT=8080
   192|
   193|# Database
   194|LIPAIRA_DB_HOST=postgres
   195|LIPAIRA_DB_PORT=5432
   196|LIPAIRA_DB_USER=lipaira
   197|LIPAIRA_DB_PASSWORD=***
   198|LIPAIRA_DB_NAME=lipaira
   199|
   200|# Redis
   201|LIPAIRA_REDIS_HOST=redis
   202|LIPAIRA_REDIS_PORT=6379
   203|
   204|# ==============================================
   205|# BILLING
   206|# ==============================================
   207|# All billing is handled by Lipaira (us).
   208|# Users buy credits from us through our server.
   209|# 
   210|# Self-hosted mode means user runs the OS on their VPS,
   211|# but it connects to our server for billing + LLM routing.
   212|# ==============================================
   213|
   214|# Connection to Lipaira cloud (REQUIRED for billing)
   215|LIPAIRA_API_URL=https://api.lipaira.ai
   216|LIPAIRA_API_KEY=***  # Get from lipaira.ai dashboard
   217|
   218|# Security
   219|LIPAIRA_SANDBOX_ENABLED=true
   220|LIPAIRA_ALLOW_NETWORK=false
   221|
   222|# Logging
   223|LIPAIRA_LOG_LEVEL=info
   224|EOF
   225|
   226|    # Copy to data dir
   227|    cp "$LIPAIRA_CONFIG_DIR/env" "$LIPAIRA_DIR/.env"
   228|    
   229|    log "Configuration generated at $LIPAIRA_CONFIG_DIR/env"
   230|}
   231|
   232|# Pull images
   233|pull_images() {
   234|    log "Pulling Docker images (this may take a few minutes)..."
   235|    
   236|    cd "$LIPAIRA_DIR"
   237|    
   238|    # For now, we'll build from local code if available
   239|    # In production, we'd have a registry
   240|    if [ -d "/data/.openclaw/workspace/nexusos" ]; then
   241|        warn "Building from local source..."
   242|        # Build locally for now
   243|    else
   244|        info "To deploy: get API key from https://lipaira.ai"
   245|    fi
   246|}
   247|
   248|# Setup systemd service
   249|setup_service() {
   250|    log "Setting up systemd service..."
   251|    
   252|    cat > /etc/systemd/system/lipaira.service << 'EOF'
   253|[Unit]
   254|Description=Lipaira AI Agent OS
   255|After=network.target docker.service
   256|Requires=docker.service
   257|
   258|[Service]
   259|Type=oneshot
   260|RemainAfterExit=yes
   261|WorkingDirectory=/opt/lipaira
   262|ExecStart=/usr/bin/docker compose up -d
   263|ExecStop=/usr/bin/docker compose down
   264|TimeoutStartSec=0
   265|
   266|[Install]
   267|WantedBy=multi-user.target
   268|EOF
   269|
   270|    systemctl daemon-reload
   271|    systemctl enable lipaira.service
   272|    
   273|    log "System service installed"
   274|}
   275|
   276|# Create CLI tool
   277|create_cli() {
   278|    log "Installing Lipaira CLI..."
   279|    
   280|    cat > /usr/local/bin/lipaira << 'EOF'
   281|#!/bin/bash
   282|
   283|LIPAIRA_DIR="/opt/lipaira"
   284|
   285|case "$1" in
   286|    start)
   287|        cd "$LIPAIRA_DIR" && docker compose up -d
   288|        ;;
   289|    stop)
   290|        cd "$LIPAIRA_DIR" && docker compose down
   291|        ;;
   292|    restart)
   293|        cd "$LIPAIRA_DIR" && docker compose restart
   294|        ;;
   295|    status)
   296|        cd "$LIPAIRA_DIR" && docker compose ps
   297|        ;;
   298|    logs)
   299|        docker compose logs -f "${2:-}"
   300|        ;;
   301|    config)
   302|        nano "$LIPAIRA_CONFIG_DIR/env"
   303|        ;;
   304|    update)
   305|        cd "$LIPAIRA_DIR" && docker compose pull && docker compose up -d
   306|        ;;
   307|    *)
   308|        echo "Lipaira OS CLI"
   309|        echo ""
   310|        echo "Usage: lipaira <command>"
   311|        echo ""
   312|        echo "Commands:"
   313|        echo "  start     - Start Lipaira OS"
   314|        echo "  stop      - Stop Lipaira OS"
   315|        echo "  restart   - Restart Lipaira OS"
   316|        echo "  status    - Show status"
   317|        echo "  logs      - View logs"
   318|        echo "  config    - Edit configuration"
   319|        echo "  update    - Update to latest version"
   320|        ;;
   321|esac
   322|EOF
   323|
   324|    chmod +x /usr/local/bin/lipaira
   325|    log "CLI installed: lipaira start|stop|restart|status|logs|config|update"
   326|}
   327|
   328|# Print next steps
   329|print_next_steps() {
   330|    echo ""
   331|    echo "========================================"
   332|    echo -e "${GREEN}Installation Complete!${NC}"
   333|    echo "========================================"
   334|    echo ""
   335|    echo "Next steps:"
   336|    echo ""
   337|    echo "1. Get API key:"
   338|    echo "   Sign up at https://lipaira.ai and get your API key"
   339|    echo "   Edit /etc/lipaira/env and add LIPAIRA_API_KEY=***
   340|    echo ""
   341|    echo "2. Start Lipaira OS:"
   342|    echo "   sudo lipaira start"
   343|    echo ""
   344|    echo "3. Check status:"
   345|    echo "   sudo lipaira status"
   346|    echo ""
   347|    echo "4. View logs:"
   348|    echo "   sudo lipaira logs"
   349|    echo ""
   350|    echo "========================================"
   351|    echo ""
   352|    info "Access the web UI at: http://$(hostname -I | awk '{print $1}')"
   353|    echo ""
   354|}
   355|
   356|# Main
   357|main() {
   358|    log "Lipaira OS Installer v$LIPAIRA_VERSION"
   359|    log "========================================"
   360|    
   361|    check_root
   362|    check_prereqs
   363|    create_dirs
   364|    download_compose
   365|    generate_config
   366|    create_cli
   367|    setup_service
   368|    
   369|    print_next_steps
   370|}
   371|
   372|main "$@"