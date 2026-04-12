# feel free to ignore this comment
     1|#!/bin/bash
     2|# NexusOS Docker Test Suite
     3|# Tests all components of the NexusOS Docker image
     4|
     5|set -e
     6|
     7|RED='\033[0;31m'
     8|GREEN='\033[0;32m'
     9|YELLOW='\033[1;33m'
    10|BLUE='\033[0;34m'
    11|NC='\033[0m'
    12|
    13|PASSED=0
    14|FAILED=0
    15|
    16|log_pass() { echo -e "${GREEN}✓ PASS:${NC} $1"; ((PASSED++)); }
    17|log_fail() { echo -e "${RED}✗ FAIL:${NC} $1"; ((FAILED++)); }
    18|log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
    19|log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
    20|
    21|cleanup() {
    22|    log_info "Cleaning up..."
    23|    docker-compose down --volumes --remove-orphans 2>/dev/null || true
    24|}
    25|
    26|# Trap to cleanup on exit
    27|trap cleanup EXIT
    28|
    29|echo "╔══════════════════════════════════════════╗"
    30|echo "║      NexusOS Docker Test Suite           ║"
    31|echo "╚══════════════════════════════════════════╝"
    32|echo ""
    33|
    34|# Check prerequisites
    35|log_info "Checking prerequisites..."
    36|
    37|command -v docker >/dev/null 2>&1 || { log_fail "Docker not found"; exit 1; }
    38|command -v docker-compose >/dev/null 2>&1 || { log_fail "docker-compose not found"; exit 1; }
    39|log_pass "Prerequisites"
    40|
    41|# Build the image
    42|log_info "Building Docker image..."
    43|docker-compose build --no-cache nexusos 2>&1 | tail -20
    44|if [ $? -eq 0 ]; then
    45|    log_pass "Docker image builds"
    46|else
    47|    log_fail "Docker image build failed"
    48|    exit 1
    49|fi
    50|
    51|# Start services
    52|log_info "Starting NexusOS..."
    53|docker-compose up -d
    54|
    55|# Wait for services to start
    56|log_info "Waiting for services to initialize..."
    57|sleep 10
    58|
    59|# Test 1: Memory server is running
    60|log_info "Testing Memory Server (port 4893)..."
    61|for i in {1..10}; do
    62|    if curl -s http://localhost:4893/health >/dev/null 2>&1; then
    63|        log_pass "Memory server responds"
    64|        break
    65|    fi
    66|    if [ $i -eq 10 ]; then
    67|        log_fail "Memory server not responding"
    68|        docker logs nexusos 2>&1 | tail -20
    69|    fi
    70|    sleep 2
    71|done
    72|
    73|# Test 2: Filesystem MCP
    74|log_info "Testing Filesystem MCP (port 4894)..."
    75|for i in {1..5}; do
    76|    if curl -s http://localhost:4894/health >/dev/null 2>&1; then
    77|        log_pass "Filesystem MCP responds"
    78|        break
    79|    fi
    80|    if [ $i -eq 5 ]; then
    81|        log_fail "Filesystem MCP not responding"
    82|    fi
    83|    sleep 1
    84|done
    85|
    86|# Test 3: Process MCP
    87|log_info "Testing Process MCP (port 4895)..."
    88|for i in {1..5}; do
    89|    if curl -s http://localhost:4895/health >/dev/null 2>&1; then
    90|        log_pass "Process MCP responds"
    91|        break
    92|    fi
    93|    if [ $i -eq 5 ]; then
    94|        log_fail "Process MCP not responding"
    95|    fi
    96|    sleep 1
    97|done
    98|
    99|# Test 4: HTTP MCP
   100|log_info "Testing HTTP MCP (port 4896)..."
   101|for i in {1..5}; do
   102|    if curl -s http://localhost:4896/health >/dev/null 2>&1; then
   103|        log_pass "HTTP MCP responds"
   104|        break
   105|    fi
   106|    if [ $i -eq 5 ]; then
   107|        log_fail "HTTP MCP not responding"
   108|    fi
   109|    sleep 1
   110|done
   111|
   112|# Test 5: Memory write/read
   113|log_info "Testing memory write..."
   114|RESPONSE=$(curl -s -X POST http://localhost:4893/memory/semantic/entity \
   115|    -H "Content-Type: application/json" \
   116|    -d '{"name": "test_entity", "type": "test", "properties": {"key": "value"}}')
   117|echo "$RESPONSE" | grep -q "id" && log_pass "Memory write works" || log_fail "Memory write failed"
   118|
   119|# Test 6: Memory retrieval
   120|log_info "Testing memory retrieval..."
   121|RESPONSE=$(curl -s "http://localhost:4893/memory/semantic/entity?name=test_entity")
   122|echo "$RESPONSE" | grep -q "test_entity" && log_pass "Memory retrieval works" || log_fail "Memory retrieval failed"
   123|
   124|# Test 7: Filesystem MCP - read
   125|log_info "Testing filesystem read..."
   126|echo "test content" > /tmp/nexus_test.txt
   127|RESPONSE=$(curl -s -X POST http://localhost:4894/ \
   128|    -H "Content-Type: application/json" \
   129|    -d '{"method": "read", "params": {"path": "/tmp/nexus_test.txt"}}')
   130|echo "$RESPONSE" | grep -q "test content" && log_pass "Filesystem read works" || log_fail "Filesystem read failed"
   131|
   132|# Test 8: Process MCP - list allowed
   133|log_info "Testing process list..."
   134|RESPONSE=$(curl -s -X POST http://localhost:4895/ \
   135|    -H "Content-Type: application/json" \
   136|    -d '{"method": "list_allowed", "params": {}}')
   137|echo "$RESPONSE" | grep -q "allowed" && log_pass "Process list works" || log_fail "Process list failed"
   138|
   139|# Test 9: Process MCP - execute
   140|log_info "Testing process execute..."
   141|RESPONSE=$(curl -s -X POST http://localhost:4895/ \
   142|    -H "Content-Type: application/json" \
   143|    -d '{"method": "execute", "params": {"command": "echo hello_nexus"}}')
   144|echo "$RESPONSE" | grep -q "hello_nexus" && log_pass "Process execute works" || log_fail "Process execute failed"
   145|
   146|# Test 10: HTTP MCP - GET request
   147|log_info "Testing HTTP GET..."
   148|RESPONSE=$(curl -s -X POST http://localhost:4896/ \
   149|    -H "Content-Type: application/json" \
   150|    -d '{"method": "get", "params": {"url": "https://httpbin.org/get"}}')
   151|echo "$RESPONSE" | grep -q '"url"' && log_pass "HTTP GET works" || log_fail "HTTP GET failed"
   152|
   153|# Test 11: Container health
   154|log_info "Testing container health..."
   155|docker inspect --format='{{.State.Health.Status}}' nexusos 2>/dev/null | grep -q "healthy" && log_pass "Container healthy" || log_warn "Health check not configured"
   156|
   157|# Summary
   158|echo ""
   159|echo "╔══════════════════════════════════════════╗"
   160|echo "║           Test Results                   ║"
   161|echo "╠══════════════════════════════════════════╣"
   162|echo -e "║ ${GREEN}Passed:${NC} $PASSED                              ║"
   163|if [ $FAILED -gt 0 ]; then
   164|    echo -e "║ ${RED}Failed:${NC} $FAILED                              ║"
   165|else
   166|    echo -e "║ Failed: 0                              ║"
   167|fi
   168|echo "╚══════════════════════════════════════════╝"
   169|
   170|if [ $FAILED -gt 0 ]; then
   171|    log_warn "Some tests failed - check logs above"
   172|    exit 1
   173|else
   174|    log_info "All tests passed! 🎉"
   175|fi