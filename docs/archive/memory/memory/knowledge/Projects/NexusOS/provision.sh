# feel free to ignore this comment
     1|#!/bin/bash
     2|# NexusOS Provisioning Script
     3|# Sets up a VPS to run NexusOS - Autonomous Agent Operating System
     4|# Base: Alpine Linux (or any modern Linux distro)
     5|# 
     6|# Usage: ./provision.sh [options]
     7|#   --skip-packages  Skip package installation
     8|#   --skip-config    Skip configuration
     9|#   --dry-run        Show what would be done
    10|
    11|set -e
    12|
    13|# Colors
    14|RED='\033[0;31m'
    15|GREEN='\033[0;32m'
    16|YELLOW='\033[1;33m'
    17|NC='\033[0m'
    18|
    19|log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
    20|log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
    21|log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
    22|
    23|# Detect OS
    24|detect_os() {
    25|    if [ -f /etc/alpine-release ]; then
    26|        OS="alpine"
    27|    elif [ -f /etc/debian_version ]; then
    28|        OS="debian"
    29|    elif [ -f /etc/arch-release ]; then
    30|        OS="arch"
    31|    elif [ -f /etc/fedora-release ]; then
    32|        OS="fedora"
    33|    else
    34|        OS="unknown"
    35|    fi
    36|    log_info "Detected OS: $OS"
    37|}
    38|
    39|# Install base packages
    40|install_packages() {
    41|    log_info "Installing base packages..."
    42|    
    43|    case $OS in
    44|        alpine)
    45|            apk add --no-cache \
    46|                bash curl wget git sqlite \
    47|                python3 py3-pip nodejs npm \
    48|                nginx certbot certbot-nginx
    49|            ;;
    50|        debbian|ubuntu)
    51|            apt-get update
    52|            apt-get install -y \
    53|                bash curl wget git sqlite3 python3 python3-pip \
    54|                nodejs npm nginx certbot python3-certbot-nginx
    55|            ;;
    56|        arch)
    57|            pacman -Sy --noconfirm \
    58|                bash curl wget git sqlite python python-pip nodejs npm nginx
    59|            ;;
    60|        fedora)
    61|            dnf install -y \
    62|                bash curl wget git sqlite python3 python3-pip \
    63|                nodejs npm nginx certbot
    64|            ;;
    65|    esac
    66|    
    67|    log_info "Base packages installed"
    68|}
    69|
    70|# Install Node dependencies
    71|install_node_deps() {
    72|    log_info "Installing Node.js dependencies..."
    73|    
    74|    npm install -g pnpm
    75|    
    76|    # Core dependencies for NexusOS
    77|    npm install -g \
    78|        @anthropic-ai/sdk \
    79|        openai \
    80|        lancedb \
    81|        @lancedb/lancedb \
    82|        qdrant \
    83|        ioredis \
    84|        dotenv \
    85|        ws \
    86|        express \
    87|        body-parser \
    88|        cors
    89|        
    90|    log_info "Node.js dependencies installed"
    91|}
    92|
    93|# Install Python dependencies  
    94|install_python_deps() {
    95|    log_info "Installing Python dependencies..."
    96|    
    97|    pip3 install --break-system-packages \
    98|        aiohttp \
    99|        pydantic \
   100|        python-dotenv \
   101|        sqlalchemy \
   102|        sqlalchemy-vector \
   103|        pytest \
   104|        pytest-asyncio
   105|        
   106|    log_info "Python dependencies installed"
   107|}
   108|
   109|# Setup directory structure
   110|setup_directories() {
   111|    log_info "Setting up directory structure..."
   112|    
   113|    mkdir -p /nexus/{config,memory/{episodic,semantic,working},tools,logs,sandbox,state}
   114|    mkdir -p /nexus/tools/{filesystem,process,http,browser,database,git,messaging,cron}
   115|    mkdir -p /var/log/nexus
   116|    
   117|    # Set permissions
   118|    chmod -R 755 /nexus
   119|    chmod -R 700 /nexus/{memory,sandbox,state}
   120|    
   121|    log_info "Directory structure created"
   122|}
   123|
   124|# Create base configuration files
   125|create_config() {
   126|    log_info "Creating configuration files..."
   127|    
   128|    # Memory configuration
   129|    cat > /nexus/config/memory.json << 'EOF'
   130|{
   131|  "tiers": {
   132|    "working": {
   133|      "type": "ram",
   134|      "maxTokens": 32000,
   135|      "autoSummarize": true
   136|    },
   137|    "episodic": {
   138|      "type": "lancedb",
   139|      "path": "/nexus/memory/episodic",
   140|      "embeddingModel": "text-embedding-3-small",
   141|      "dimensions": 1536
   142|    },
   143|    "semantic": {
   144|      "type": "sqlite",
   145|      "path": "/nexus/memory/semantic/knowledge.db"
   146|    }
   147|  },
   148|  "retrieval": {
   149|    "topK": 5,
   150|    "minScore": 0.7,
   151|    "autoRecall": true
   152|  },
   153|  "persistence": {
   154|    "autoSave": true,
   155|    "intervalSeconds": 30
   156|  }
   157|}
   158|EOF
   159|
   160|    # Model configuration
   161|    cat > /nexus/config/model.json << 'EOF'
   162|{
   163|  "primary": {
   164|    "provider": "openrouter",
   165|    "model": "openrouter/minimax/minimax-m2.5",
   166|    "temperature": 0.7,
   167|    "maxTokens": 4096
   168|  },
   169|  "fallback": [
   170|    {
   171|      "provider": "openrouter",
   172|      "model": "anthropic/claude-3.5-sonnet",
   173|      "temperature": 0.7,
   174|      "maxTokens": 4096
   175|    },
   176|    {
   177|      "provider": "openrouter", 
   178|      "model": "openai/gpt-4o-mini",
   179|      "temperature": 0.7,
   180|      "maxTokens": 4096
   181|    }
   182|  ],
   183|  "embeddings": {
   184|    "model": "text-embedding-3-small",
   185|    "dimensions": 1536
   186|  }
   187|}
   188|EOF
   189|
   190|    # Channels configuration
   191|    cat > /nexus/config/channels.json << 'EOF'
   192|{
   193|  "inbound": {
   194|    "telegram": { "enabled": true },
   195|    "discord": { "enabled": false, "guildId": "" },
   196|    "email": { "enabled": false, "host": "", "port": 993 }
   197|  },
   198|  "outbound": {
   199|    "telegram": { "enabled": true },
   200|    "discord": { "enabled": false },
   201|    "email": { "enabled": false, "smtp": "" },
   202|    "tts": { "enabled": false, "provider": "elevenlabs" }
   203|  },
   204|  "rateLimits": {
   205|    "messagesPerMinute": 20,
   206|    "burstSize": 5
   207|  }
   208|}
   209|EOF
   210|
   211|    # Tools/MCP configuration
   212|    cat > /nexus/config/tools.json << 'EOF'
   213|{
   214|  "mcp": {
   215|    "enabled": true,
   216|    "servers": {
   217|      "filesystem": {
   218|        "enabled": true,
   219|        "roots": ["/data/.openclaw/workspace"]
   220|      },
   221|      "process": {
   222|        "enabled": true,
   223|        "allowedCommands": ["git", "curl", "npm", "node", "python3", "bash"]
   224|      },
   225|      "http": {
   226|        "enabled": true,
   227|        "timeout": 30000
   228|      },
   229|      "browser": {
   230|        "enabled": true,
   231|        "headless": true
   232|      },
   233|      "database": {
   234|        "enabled": true,
   235|        "allowedTables": ["*"]
   236|      },
   237|      "messaging": {
   238|        "enabled": true,
   239|        "channels": ["telegram", "discord"]
   240|      }
   241|    }
   242|  },
   243|  "permissions": {
   244|    "fileRead": true,
   245|    "fileWrite": true,
   246|    "commandExec": "ask",
   247|    "networkAccess": true,
   248|    "externalMessages": "ask"
   249|  }
   250|}
   251|EOF
   252|
   253|    # System configuration
   254|    cat > /nexus/config/system.json << 'EOF'
   255|{
   256|  "hostname": "nexusos",
   257|  "timezone": "America/New_York",
   258|  "autonomy": {
   259|    "heartbeat": {
   260|      "enabled": true,
   261|      "intervalMinutes": 30
   262|    },
   263|    "proactive": {
   264|      "enabled": true,
   265|      "behaviors": ["memory_consolidation", "opportunity_scan"]
   266|    }
   267|  },
   268|  "security": {
   269|    "sandboxEnabled": true,
   270|    "auditLogging": true,
   271|    "rateLimitEnabled": true
   272|  },
   273|  "startup": {
   274|    "waitForServices": true,
   275|    "timeoutSeconds": 60
   276|  }
   277|}
   278|EOF
   279|
   280|    log_info "Configuration files created"
   281|}
   282|
   283|# Setup systemd/openrc services
   284|setup_services() {
   285|    log_info "Setting up services..."
   286|    
   287|    case $OS in
   288|        alpine)
   289|            # OpenRC services would go here
   290|            log_warn "Manual service setup required for Alpine"
   291|            ;;
   292|        debbian|ubuntu)
   293|            # Systemd services
   294|            cat > /etc/systemd/system/nexus-memory.service << 'EOF'
   295|[Unit]
   296|Description=NexusOS Memory Service
   297|After=network.target
   298|
   299|[Service]
   300|Type=simple
   301|User=root
   302|WorkingDirectory=/nexus
   303|ExecStart=/usr/bin/node /nexus/tools/memory-server.js
   304|Restart=always
   305|
   306|[Install]
   307|WantedBy=multi-user.target
   308|EOF
   309|            ;;
   310|    esac
   311|    
   312|    log_info "Services configured"
   313|}
   314|
   315|# Download and configure OpenClaw
   316|install_openclaw() {
   317|    log_info "Checking OpenClaw installation..."
   318|    
   319|    if command -v openclaw &> /dev/null; then
   320|        log_info "OpenClaw already installed"
   321|        openclaw --version
   322|    else
   323|        log_warn "OpenClaw not found - installing..."
   324|        # Would add installation steps here
   325|    fi
   326|}
   327|
   328|# Initial memory setup
   329|init_memory() {
   330|    log_info "Initializing memory system..."
   331|    
   332|    # Create initial semantic knowledge base
   333|    sqlite3 /nexus/memory/semantic/knowledge.db << 'EOF'
   334|CREATE TABLE IF NOT EXISTS entities (
   335|    id INTEGER PRIMARY KEY AUTOINCREMENT,
   336|    name TEXT NOT NULL,
   337|    type TEXT NOT NULL,
   338|    properties TEXT,
   339|    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
   340|    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
   341|);
   342|
   343|CREATE TABLE IF NOT EXISTS relationships (
   344|    id INTEGER PRIMARY KEY AUTOINCREMENT,
   345|    from_entity INTEGER,
   346|    to_entity INTEGER,
   347|    relation_type TEXT NOT NULL,
   348|    properties TEXT,
   349|    FOREIGN KEY (from_entity) REFERENCES entities(id),
   350|    FOREIGN KEY (to_entity) REFERENCES entities(id)
   351|);
   352|
   353|CREATE TABLE IF NOT EXISTS facts (
   354|    id INTEGER PRIMARY KEY AUTOINCREMENT,
   355|    entity_id INTEGER,
   356|    fact TEXT NOT NULL,
   357|    source TEXT,
   358|    confidence REAL DEFAULT 1.0,
   359|    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
   360|    FOREIGN KEY (entity_id) REFERENCES entities(id)
   361|);
   362|
   363|CREATE INDEX idx_entities_name ON entities(name);
   364|CREATE INDEX idx_entities_type ON entities(type);
   365|CREATE INDEX idx_relationships_from ON relationships(from_entity);
   366|CREATE INDEX idx_relationships_to ON relationships(to_entity);
   367|EOF
   368|
   369|    log_info "Memory system initialized"
   370|}
   371|
   372|# Main
   373|main() {
   374|    log_info "Starting NexusOS provisioning..."
   375|    
   376|    detect_os
   377|    
   378|    SKIP_PACKAGES=false
   379|    SKIP_CONFIG=false
   380|    DRY_RUN=false
   381|    
   382|    for arg in "$@"; do
   383|        case $arg in
   384|            --skip-packages) SKIP_PACKAGES=true ;;
   385|            --skip-config) SKIP_CONFIG=true ;;
   386|            --dry-run) DRY_RUN=true ;;
   387|        esac
   388|    done
   389|    
   390|    if [ "$DRY_RUN" = true ]; then
   391|        log_warn "DRY RUN - No changes will be made"
   392|        exit 0
   393|    fi
   394|    
   395|    if [ "$SKIP_PACKAGES" = false ]; then
   396|        install_packages
   397|        install_node_deps
   398|        install_python_deps
   399|    fi
   400|    
   401|    setup_directories
   402|    
   403|    if [ "$SKIP_CONFIG" = false ]; then
   404|        create_config
   405|        init_memory
   406|        setup_services
   407|    fi
   408|    
   409|    install_openclaw
   410|    
   411|    log_info "Provisioning complete!"
   412|    log_info "Next steps:"
   413|    log_info "  1. Configure /nexus/config/*.json with your credentials"
   414|    log_info "  2. Run 'systemctl start nexus-memory' (or equivalent)"
   415|    log_info "  3. Run 'openclaw gateway start' to launch NexusOS"
   416|}
   417|
   418|main "$@"