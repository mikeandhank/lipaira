# feel free to ignore this comment
     1|#!/bin/bash
     2|set -e
     3|
     4|echo "╔══════════════════════════════════════════╗"
     5|echo "║         NexusOS Starting...              ║"
     6|echo "╚══════════════════════════════════════════╝"
     7|
     8|# Colors
     9|RED='\033[0;31m'
    10|GREEN='\033[0;32m'
    11|YELLOW='\033[1;33m'
    12|BLUE='\033[0;34m'
    13|NC='\033[0m'
    14|
    15|log_info() { echo -e "${GREEN}[NexusOS]${NC} $1"; }
    16|log_warn() { echo -e "${YELLOW}[NexusOS]${NC} $1"; }
    17|log_error() { echo -e "${RED}[NexusOS]${NC} $1"; }
    18|
    19|# Check environment
    20|log_info "Environment: ${NEXUS_ENV:-development}"
    21|
    22|# Initialize memory directories
    23|log_info "Initializing memory directories..."
    24|mkdir -p /nexus/memory/{episodic,semantic,working}
    25|mkdir -p /nexus/logs
    26|mkdir -p /nexus/sandbox
    27|mkdir -p /nexus/state
    28|
    29|# Initialize SQLite database if not exists
    30|if [ ! -f /nexus/memory/semantic/knowledge.db ]; then
    31|    log_info "Creating semantic memory database..."
    32|    sqlite3 /nexus/memory/semantic/knowledge.db << 'EOF'
    33|CREATE TABLE IF NOT EXISTS entities (
    34|    id INTEGER PRIMARY KEY AUTOINCREMENT,
    35|    name TEXT NOT NULL,
    36|    type TEXT NOT NULL,
    37|    properties TEXT,
    38|    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    39|    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    40|);
    41|
    42|CREATE TABLE IF NOT EXISTS relationships (
    43|    id INTEGER PRIMARY KEY AUTOINCREMENT,
    44|    from_entity INTEGER,
    45|    to_entity INTEGER,
    46|    relation_type TEXT NOT NULL,
    47|    properties TEXT,
    48|    FOREIGN KEY (from_entity) REFERENCES entities(id),
    49|    FOREIGN KEY (to_entity) REFERENCES entities(id)
    50|);
    51|
    52|CREATE TABLE IF NOT EXISTS facts (
    53|    id INTEGER PRIMARY KEY AUTOINCREMENT,
    54|    entity_id INTEGER,
    55|    fact TEXT NOT NULL,
    56|    source TEXT,
    57|    confidence REAL DEFAULT 1.0,
    58|    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    59|    FOREIGN KEY (entity_id) REFERENCES entities(id)
    60|);
    61|
    62|CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
    63|CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
    64|CREATE INDEX IF NOT EXISTS idx_relationships_from ON relationships(from_entity);
    65|CREATE INDEX IF NOT EXISTS idx_relationships_to ON relationships(to_entity);
    66|EOF
    67|    log_info "Semantic memory initialized"
    68|fi
    69|
    70|# Start Memory Server in background (THIS WAS MISSING!)
    71|log_info "Starting Memory Server (port 4893)..."
    72|cd /home/nexus
    73|node tools/memory-server.js > /nexus/logs/memory-server.log 2>&1 &
    74|echo $! > /nexus/state/memory-server.pid
    75|
    76|# Start MCP servers in background
    77|log_info "Starting MCP servers..."
    78|
    79|cd /home/nexus
    80|python3 tools/mcp-filesystem/server.py > /nexus/logs/mcp-filesystem.log 2>&1 &
    81|echo $! > /nexus/state/mcp-filesystem.pid
    82|
    83|python3 tools/mcp-process/server.py > /nexus/logs/mcp-process.log 2>&1 &
    84|echo $! > /nexus/state/mcp-process.pid
    85|
    86|python3 tools/mcp-http/server.py > /nexus/logs/mcp-http.log 2>&1 &
    87|echo $! > /nexus/state/mcp-http.pid
    88|
    89|# Wait for servers to start
    90|log_info "Waiting for services to initialize..."
    91|sleep 3
    92|
    93|# Check services using wget (available in Alpine)
    94|check_service() {
    95|    local port=$1
    96|    local name=$2
    97|    if wget -q --spider "http://localhost:$port/health" 2>/dev/null; then
    98|        log_info "$name: ✓ Running on port $port"
    99|        return 0
   100|    else
   101|        log_warn "$name: ✗ Not responding on port $port"
   102|        return 1
   103|    fi
   104|}
   105|
   106|check_service 4893 "Memory Server" || true
   107|check_service 4894 "Filesystem MCP" || true
   108|check_service 4895 "Process MCP" || true
   109|check_service 4896 "HTTP MCP" || true
   110|
   111|# Show running processes
   112|log_info "Running services:"
   113|ps aux | grep -E "(memory-server|mcp-)" | grep -v grep || log_warn "No MCP processes found"
   114|
   115|# Summary
   116|echo ""
   117|echo "╔══════════════════════════════════════════╗"
   118|echo "║         NexusOS Ready                    ║"
   119|echo "╠══════════════════════════════════════════╣"
   120|echo "║ Memory:     http://localhost:4893        ║"
   121|echo "║ Filesystem: http://localhost:4894        ║"
   122|echo "║ Process:    http://localhost:4895        ║"
   123|echo "║ HTTP:       http://localhost:4896        ║"
   124|echo "╚══════════════════════════════════════════╝"
   125|echo ""
   126|
   127|# Keep container running
   128|tail -f /dev/null