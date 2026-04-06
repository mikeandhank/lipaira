#!/bin/bash
# NexusOS Provisioning Script
# Sets up a VPS to run NexusOS - Autonomous Agent Operating System
# Base: Alpine Linux (or any modern Linux distro)
# 
# Usage: ./provision.sh [options]
#   --skip-packages  Skip package installation
#   --skip-config    Skip configuration
#   --dry-run        Show what would be done

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Detect OS
detect_os() {
    if [ -f /etc/alpine-release ]; then
        OS="alpine"
    elif [ -f /etc/debian_version ]; then
        OS="debian"
    elif [ -f /etc/arch-release ]; then
        OS="arch"
    elif [ -f /etc/fedora-release ]; then
        OS="fedora"
    else
        OS="unknown"
    fi
    log_info "Detected OS: $OS"
}

# Install base packages
install_packages() {
    log_info "Installing base packages..."
    
    case $OS in
        alpine)
            apk add --no-cache \
                bash curl wget git sqlite \
                python3 py3-pip nodejs npm \
                nginx certbot certbot-nginx
            ;;
        debbian|ubuntu)
            apt-get update
            apt-get install -y \
                bash curl wget git sqlite3 python3 python3-pip \
                nodejs npm nginx certbot python3-certbot-nginx
            ;;
        arch)
            pacman -Sy --noconfirm \
                bash curl wget git sqlite python python-pip nodejs npm nginx
            ;;
        fedora)
            dnf install -y \
                bash curl wget git sqlite python3 python3-pip \
                nodejs npm nginx certbot
            ;;
    esac
    
    log_info "Base packages installed"
}

# Install Node dependencies
install_node_deps() {
    log_info "Installing Node.js dependencies..."
    
    npm install -g pnpm
    
    # Core dependencies for NexusOS
    npm install -g \
        @anthropic-ai/sdk \
        openai \
        lancedb \
        @lancedb/lancedb \
        qdrant \
        ioredis \
        dotenv \
        ws \
        express \
        body-parser \
        cors
        
    log_info "Node.js dependencies installed"
}

# Install Python dependencies  
install_python_deps() {
    log_info "Installing Python dependencies..."
    
    pip3 install --break-system-packages \
        aiohttp \
        pydantic \
        python-dotenv \
        sqlalchemy \
        sqlalchemy-vector \
        pytest \
        pytest-asyncio
        
    log_info "Python dependencies installed"
}

# Setup directory structure
setup_directories() {
    log_info "Setting up directory structure..."
    
    mkdir -p /nexus/{config,memory/{episodic,semantic,working},tools,logs,sandbox,state}
    mkdir -p /nexus/tools/{filesystem,process,http,browser,database,git,messaging,cron}
    mkdir -p /var/log/nexus
    
    # Set permissions
    chmod -R 755 /nexus
    chmod -R 700 /nexus/{memory,sandbox,state}
    
    log_info "Directory structure created"
}

# Create base configuration files
create_config() {
    log_info "Creating configuration files..."
    
    # Memory configuration
    cat > /nexus/config/memory.json << 'EOF'
{
  "tiers": {
    "working": {
      "type": "ram",
      "maxTokens": 32000,
      "autoSummarize": true
    },
    "episodic": {
      "type": "lancedb",
      "path": "/nexus/memory/episodic",
      "embeddingModel": "text-embedding-3-small",
      "dimensions": 1536
    },
    "semantic": {
      "type": "sqlite",
      "path": "/nexus/memory/semantic/knowledge.db"
    }
  },
  "retrieval": {
    "topK": 5,
    "minScore": 0.7,
    "autoRecall": true
  },
  "persistence": {
    "autoSave": true,
    "intervalSeconds": 30
  }
}
EOF

    # Model configuration
    cat > /nexus/config/model.json << 'EOF'
{
  "primary": {
    "provider": "openrouter",
    "model": "openrouter/minimax/minimax-m2.5",
    "temperature": 0.7,
    "maxTokens": 4096
  },
  "fallback": [
    {
      "provider": "openrouter",
      "model": "anthropic/claude-3.5-sonnet",
      "temperature": 0.7,
      "maxTokens": 4096
    },
    {
      "provider": "openrouter", 
      "model": "openai/gpt-4o-mini",
      "temperature": 0.7,
      "maxTokens": 4096
    }
  ],
  "embeddings": {
    "model": "text-embedding-3-small",
    "dimensions": 1536
  }
}
EOF

    # Channels configuration
    cat > /nexus/config/channels.json << 'EOF'
{
  "inbound": {
    "telegram": { "enabled": true },
    "discord": { "enabled": false, "guildId": "" },
    "email": { "enabled": false, "host": "", "port": 993 }
  },
  "outbound": {
    "telegram": { "enabled": true },
    "discord": { "enabled": false },
    "email": { "enabled": false, "smtp": "" },
    "tts": { "enabled": false, "provider": "elevenlabs" }
  },
  "rateLimits": {
    "messagesPerMinute": 20,
    "burstSize": 5
  }
}
EOF

    # Tools/MCP configuration
    cat > /nexus/config/tools.json << 'EOF'
{
  "mcp": {
    "enabled": true,
    "servers": {
      "filesystem": {
        "enabled": true,
        "roots": ["/data/.openclaw/workspace"]
      },
      "process": {
        "enabled": true,
        "allowedCommands": ["git", "curl", "npm", "node", "python3", "bash"]
      },
      "http": {
        "enabled": true,
        "timeout": 30000
      },
      "browser": {
        "enabled": true,
        "headless": true
      },
      "database": {
        "enabled": true,
        "allowedTables": ["*"]
      },
      "messaging": {
        "enabled": true,
        "channels": ["telegram", "discord"]
      }
    }
  },
  "permissions": {
    "fileRead": true,
    "fileWrite": true,
    "commandExec": "ask",
    "networkAccess": true,
    "externalMessages": "ask"
  }
}
EOF

    # System configuration
    cat > /nexus/config/system.json << 'EOF'
{
  "hostname": "nexusos",
  "timezone": "America/New_York",
  "autonomy": {
    "heartbeat": {
      "enabled": true,
      "intervalMinutes": 30
    },
    "proactive": {
      "enabled": true,
      "behaviors": ["memory_consolidation", "opportunity_scan"]
    }
  },
  "security": {
    "sandboxEnabled": true,
    "auditLogging": true,
    "rateLimitEnabled": true
  },
  "startup": {
    "waitForServices": true,
    "timeoutSeconds": 60
  }
}
EOF

    log_info "Configuration files created"
}

# Setup systemd/openrc services
setup_services() {
    log_info "Setting up services..."
    
    case $OS in
        alpine)
            # OpenRC services would go here
            log_warn "Manual service setup required for Alpine"
            ;;
        debbian|ubuntu)
            # Systemd services
            cat > /etc/systemd/system/nexus-memory.service << 'EOF'
[Unit]
Description=NexusOS Memory Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/nexus
ExecStart=/usr/bin/node /nexus/tools/memory-server.js
Restart=always

[Install]
WantedBy=multi-user.target
EOF
            ;;
    esac
    
    log_info "Services configured"
}

# Download and configure OpenClaw
install_openclaw() {
    log_info "Checking OpenClaw installation..."
    
    if command -v openclaw &> /dev/null; then
        log_info "OpenClaw already installed"
        openclaw --version
    else
        log_warn "OpenClaw not found - installing..."
        # Would add installation steps here
    fi
}

# Initial memory setup
init_memory() {
    log_info "Initializing memory system..."
    
    # Create initial semantic knowledge base
    sqlite3 /nexus/memory/semantic/knowledge.db << 'EOF'
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    properties TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_entity INTEGER,
    to_entity INTEGER,
    relation_type TEXT NOT NULL,
    properties TEXT,
    FOREIGN KEY (from_entity) REFERENCES entities(id),
    FOREIGN KEY (to_entity) REFERENCES entities(id)
);

CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER,
    fact TEXT NOT NULL,
    source TEXT,
    confidence REAL DEFAULT 1.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entity_id) REFERENCES entities(id)
);

CREATE INDEX idx_entities_name ON entities(name);
CREATE INDEX idx_entities_type ON entities(type);
CREATE INDEX idx_relationships_from ON relationships(from_entity);
CREATE INDEX idx_relationships_to ON relationships(to_entity);
EOF

    log_info "Memory system initialized"
}

# Main
main() {
    log_info "Starting NexusOS provisioning..."
    
    detect_os
    
    SKIP_PACKAGES=false
    SKIP_CONFIG=false
    DRY_RUN=false
    
    for arg in "$@"; do
        case $arg in
            --skip-packages) SKIP_PACKAGES=true ;;
            --skip-config) SKIP_CONFIG=true ;;
            --dry-run) DRY_RUN=true ;;
        esac
    done
    
    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY RUN - No changes will be made"
        exit 0
    fi
    
    if [ "$SKIP_PACKAGES" = false ]; then
        install_packages
        install_node_deps
        install_python_deps
    fi
    
    setup_directories
    
    if [ "$SKIP_CONFIG" = false ]; then
        create_config
        init_memory
        setup_services
    fi
    
    install_openclaw
    
    log_info "Provisioning complete!"
    log_info "Next steps:"
    log_info "  1. Configure /nexus/config/*.json with your credentials"
    log_info "  2. Run 'systemctl start nexus-memory' (or equivalent)"
    log_info "  3. Run 'openclaw gateway start' to launch NexusOS"
}

main "$@"