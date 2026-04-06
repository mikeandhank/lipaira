#!/bin/bash
# NexusOS Docker Test Suite
# Tests all components of the NexusOS Docker image

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASSED=0
FAILED=0

log_pass() { echo -e "${GREEN}✓ PASS:${NC} $1"; ((PASSED++)); }
log_fail() { echo -e "${RED}✗ FAIL:${NC} $1"; ((FAILED++)); }
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

cleanup() {
    log_info "Cleaning up..."
    docker-compose down --volumes --remove-orphans 2>/dev/null || true
}

# Trap to cleanup on exit
trap cleanup EXIT

echo "╔══════════════════════════════════════════╗"
echo "║      NexusOS Docker Test Suite           ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Check prerequisites
log_info "Checking prerequisites..."

command -v docker >/dev/null 2>&1 || { log_fail "Docker not found"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { log_fail "docker-compose not found"; exit 1; }
log_pass "Prerequisites"

# Build the image
log_info "Building Docker image..."
docker-compose build --no-cache nexusos 2>&1 | tail -20
if [ $? -eq 0 ]; then
    log_pass "Docker image builds"
else
    log_fail "Docker image build failed"
    exit 1
fi

# Start services
log_info "Starting NexusOS..."
docker-compose up -d

# Wait for services to start
log_info "Waiting for services to initialize..."
sleep 10

# Test 1: Memory server is running
log_info "Testing Memory Server (port 4893)..."
for i in {1..10}; do
    if curl -s http://localhost:4893/health >/dev/null 2>&1; then
        log_pass "Memory server responds"
        break
    fi
    if [ $i -eq 10 ]; then
        log_fail "Memory server not responding"
        docker logs nexusos 2>&1 | tail -20
    fi
    sleep 2
done

# Test 2: Filesystem MCP
log_info "Testing Filesystem MCP (port 4894)..."
for i in {1..5}; do
    if curl -s http://localhost:4894/health >/dev/null 2>&1; then
        log_pass "Filesystem MCP responds"
        break
    fi
    if [ $i -eq 5 ]; then
        log_fail "Filesystem MCP not responding"
    fi
    sleep 1
done

# Test 3: Process MCP
log_info "Testing Process MCP (port 4895)..."
for i in {1..5}; do
    if curl -s http://localhost:4895/health >/dev/null 2>&1; then
        log_pass "Process MCP responds"
        break
    fi
    if [ $i -eq 5 ]; then
        log_fail "Process MCP not responding"
    fi
    sleep 1
done

# Test 4: HTTP MCP
log_info "Testing HTTP MCP (port 4896)..."
for i in {1..5}; do
    if curl -s http://localhost:4896/health >/dev/null 2>&1; then
        log_pass "HTTP MCP responds"
        break
    fi
    if [ $i -eq 5 ]; then
        log_fail "HTTP MCP not responding"
    fi
    sleep 1
done

# Test 5: Memory write/read
log_info "Testing memory write..."
RESPONSE=$(curl -s -X POST http://localhost:4893/memory/semantic/entity \
    -H "Content-Type: application/json" \
    -d '{"name": "test_entity", "type": "test", "properties": {"key": "value"}}')
echo "$RESPONSE" | grep -q "id" && log_pass "Memory write works" || log_fail "Memory write failed"

# Test 6: Memory retrieval
log_info "Testing memory retrieval..."
RESPONSE=$(curl -s "http://localhost:4893/memory/semantic/entity?name=test_entity")
echo "$RESPONSE" | grep -q "test_entity" && log_pass "Memory retrieval works" || log_fail "Memory retrieval failed"

# Test 7: Filesystem MCP - read
log_info "Testing filesystem read..."
echo "test content" > /tmp/nexus_test.txt
RESPONSE=$(curl -s -X POST http://localhost:4894/ \
    -H "Content-Type: application/json" \
    -d '{"method": "read", "params": {"path": "/tmp/nexus_test.txt"}}')
echo "$RESPONSE" | grep -q "test content" && log_pass "Filesystem read works" || log_fail "Filesystem read failed"

# Test 8: Process MCP - list allowed
log_info "Testing process list..."
RESPONSE=$(curl -s -X POST http://localhost:4895/ \
    -H "Content-Type: application/json" \
    -d '{"method": "list_allowed", "params": {}}')
echo "$RESPONSE" | grep -q "allowed" && log_pass "Process list works" || log_fail "Process list failed"

# Test 9: Process MCP - execute
log_info "Testing process execute..."
RESPONSE=$(curl -s -X POST http://localhost:4895/ \
    -H "Content-Type: application/json" \
    -d '{"method": "execute", "params": {"command": "echo hello_nexus"}}')
echo "$RESPONSE" | grep -q "hello_nexus" && log_pass "Process execute works" || log_fail "Process execute failed"

# Test 10: HTTP MCP - GET request
log_info "Testing HTTP GET..."
RESPONSE=$(curl -s -X POST http://localhost:4896/ \
    -H "Content-Type: application/json" \
    -d '{"method": "get", "params": {"url": "https://httpbin.org/get"}}')
echo "$RESPONSE" | grep -q '"url"' && log_pass "HTTP GET works" || log_fail "HTTP GET failed"

# Test 11: Container health
log_info "Testing container health..."
docker inspect --format='{{.State.Health.Status}}' nexusos 2>/dev/null | grep -q "healthy" && log_pass "Container healthy" || log_warn "Health check not configured"

# Summary
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║           Test Results                   ║"
echo "╠══════════════════════════════════════════╣"
echo -e "║ ${GREEN}Passed:${NC} $PASSED                              ║"
if [ $FAILED -gt 0 ]; then
    echo -e "║ ${RED}Failed:${NC} $FAILED                              ║"
else
    echo -e "║ Failed: 0                              ║"
fi
echo "╚══════════════════════════════════════════╝"

if [ $FAILED -gt 0 ]; then
    log_warn "Some tests failed - check logs above"
    exit 1
else
    log_info "All tests passed! 🎉"
fi