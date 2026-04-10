#!/bin/bash
set -e

BASE_URL="https://api.lipaira.ai"
FREE_KEY="${LIPAIRA_FREE_TEST_KEY}"
PASS=0
FAIL=0

echo "=== Lipaira Production Verification ==="
echo "Timestamp: $(date -u)"
echo "========================================"

# Test 1: Health check
echo ""
echo "--- Test 1: Health Check ---"
HEALTH=$(curl -sf $BASE_URL/health 2>/dev/null || echo "FAILED")
if echo "$HEALTH" | grep -q '"status":"ok"'; then
    echo "PASS: Health check OK"
    PASS=$((PASS + 1))
else
    echo "FAIL: Health check returned: $HEALTH"
    FAIL=$((FAIL + 1))
fi

# Test 2: Auth enforcement
echo ""
echo "--- Test 2: Auth Enforcement ---"
curl -s -o /dev/null -w "%{http_code}" $BASE_URL/api/chat \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{"message":"test"}' > /tmp/auth_status.txt 2>/dev/null
read AUTH_STATUS < /tmp/auth_status.txt
if [ "$AUTH_STATUS" = "401" ]; then
    echo "PASS: Unauthenticated request correctly rejected (401)"
    PASS=$((PASS + 1))
else
    echo "FAIL: Expected 401, got $AUTH_STATUS"
    FAIL=$((FAIL + 1))
fi

# Test 3: Free tier read
echo ""
echo "--- Test 3: Free Tier Read (B2-A) ---"
if [ -z "$FREE_KEY" ]; then
    echo "SKIP: LIPAIRA_FREE_TEST_KEY not configured"
else
    READ_RESPONSE=$(curl -s -X POST $BASE_URL/api/chat \
        -H "X-Lipaira-Key: $FREE_KEY" \
        -H "Content-Type: application/json" \
        -d '{"message":"what invoices do I have open?"}')
    if echo "$READ_RESPONSE" | grep -q '"success":true'; then
        echo "PASS: Free tier read executed successfully"
        PASS=$((PASS + 1))
    else
        echo "FAIL: Free tier read failed: $READ_RESPONSE"
        FAIL=$((FAIL + 1))
    fi
fi

# Test 4: Free tier write block
echo ""
echo "--- Test 4: Free Tier Write Block (B2-A) ---"
if [ -z "$FREE_KEY" ]; then
    echo "SKIP: LIPAIRA_FREE_TEST_KEY not configured"
else
    WRITE_RESPONSE=$(curl -s -X POST $BASE_URL/api/chat \
        -H "X-Lipaira-Key: $FREE_KEY" \
        -H "Content-Type: application/json" \
        -d '{"message":"send a chase email to Henderson"}')
    if echo "$WRITE_RESPONSE" | grep -q "Connect credits"; then
        echo "PASS: Free tier write correctly blocked"
        PASS=$((PASS + 1))
    else
        echo "FAIL: Free tier write not blocked: $WRITE_RESPONSE"
        FAIL=$((FAIL + 1))
    fi
fi

# Summary
echo ""
echo "========================================"
echo "Results: $PASS passed, $FAIL failed"
echo "========================================"

if [ $FAIL -gt 0 ]; then
    echo "VERIFICATION FAILED"
    exit 1
else
    echo "VERIFICATION PASSED"
    exit 0
fi
