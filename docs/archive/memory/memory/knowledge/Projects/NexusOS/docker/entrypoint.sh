#!/bin/bash
set -e

echo "╔══════════════════════════════════════════╗"
echo "║         NexusOS Starting...              ║"
echo "╚══════════════════════════════════════════╝"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[NexusOS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[NexusOS]${NC} $1"; }
log_error() { echo -e "${RED}[NexusOS]${NC} $1"; }

# Check environment
log_info "Environment: ${NEXUS_ENV:-development}"

# Initialize memory directories
log_info "Initializing memory directories..."
mkdir -p /nexus/memory/{episodic,semantic,working}
mkdir -p /nexus/logs
mkdir -p /nexus/sandbox
mkdir -p /nexus/state

# Initialize SQLite database if not exists
if [ ! -f /nexus/memory/semantic/knowledge.db ]; then
    log_info "Creating semantic memory database..."
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

CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_relationships_from ON relationships(from_entity);
CREATE INDEX IF NOT EXISTS idx_relationships_to ON relationships(to_entity);
EOF
    log_info "Semantic memory initialized"
fi

# Start Memory Server in background (THIS WAS MISSING!)
log_info "Starting Memory Server (port 4893)..."
cd /home/nexus
node tools/memory-server.js > /nexus/logs/memory-server.log 2>&1 &
echo $! > /nexus/state/memory-server.pid

# Start MCP servers in background
log_info "Starting MCP servers..."

cd /home/nexus
python3 tools/mcp-filesystem/server.py > /nexus/logs/mcp-filesystem.log 2>&1 &
echo $! > /nexus/state/mcp-filesystem.pid

python3 tools/mcp-process/server.py > /nexus/logs/mcp-process.log 2>&1 &
echo $! > /nexus/state/mcp-process.pid

python3 tools/mcp-http/server.py > /nexus/logs/mcp-http.log 2>&1 &
echo $! > /nexus/state/mcp-http.pid

# Wait for servers to start
log_info "Waiting for services to initialize..."
sleep 3

# Check services using wget (available in Alpine)
check_service() {
    local port=$1
    local name=$2
    if wget -q --spider "http://localhost:$port/health" 2>/dev/null; then
        log_info "$name: ✓ Running on port $port"
        return 0
    else
        log_warn "$name: ✗ Not responding on port $port"
        return 1
    fi
}

check_service 4893 "Memory Server" || true
check_service 4894 "Filesystem MCP" || true
check_service 4895 "Process MCP" || true
check_service 4896 "HTTP MCP" || true

# Show running processes
log_info "Running services:"
ps aux | grep -E "(memory-server|mcp-)" | grep -v grep || log_warn "No MCP processes found"

# Summary
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║         NexusOS Ready                    ║"
echo "╠══════════════════════════════════════════╣"
echo "║ Memory:     http://localhost:4893        ║"
echo "║ Filesystem: http://localhost:4894        ║"
echo "║ Process:    http://localhost:4895        ║"
echo "║ HTTP:       http://localhost:4896        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Keep container running
tail -f /dev/null