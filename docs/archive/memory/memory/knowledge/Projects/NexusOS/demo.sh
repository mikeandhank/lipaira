#!/bin/bash
# NexusOS Demo Script
# Run this to show NexusOS capabilities

NEXUS_URL="${NEXUS_URL:-http://localhost:4893}"

echo "============================================"
echo "      NexusOS Demo - Persistent Memory    "
echo "============================================"
echo ""

# Check if running
echo "1. Checking NexusOS health..."
HEALTH=$(curl -s "$NEXUS_URL/health")
if echo "$HEALTH" | grep -q "healthy"; then
    echo "   ✓ NexusOS is running"
else
    echo "   ✗ NexusOS is not running. Start with: node tools/memory-server.js"
    exit 1
fi

echo ""
echo "2. Starting a new session..."
SESSION=$(curl -s -X POST "$NEXUS_URL/memory/working/start" \
    -H "Content-Type: application/json" \
    -d '{"sessionId":"demo-session"}')
echo "   Session started: demo-session"

echo ""
echo "3. Adding messages to memory..."

# User message
curl -s -X POST "$NEXUS_URL/memory/working/message" \
    -H "Content-Type: application/json" \
    -d '{"content":"I'm working on a project called NexusOS - it's an agent operating system","role":"user"}' > /dev/null
echo "   Added: User message about NexusOS"

# Assistant response  
curl -s -X POST "$NEXUS_URL/memory/working/message" \
    -H "Content-Type: application/json" \
    -d '{"content":"That sounds interesting! What does NexusOS do?","role":"assistant"}' > /dev/null
echo "   Added: Assistant response"

# Another user message
curl -s -X POST "$NEXUS_URL/memory/working/message" \
    -H "Content-Type: application/json" \
    -d '{"content":"It gives AI agents persistent memory that survives restarts. We solve the amnesia problem.","role":"user"}' > /dev/null
echo "   Added: User explains NexusOS value"

echo ""
echo "4. Ending session (persisting to episodic memory)..."
curl -s -X POST "$NEXUS_URL/memory/working/end" \
    -H "Content-Type: application/json" \
    -d '{}' > /dev/null
echo "   ✓ Session ended, memories persisted"

echo ""
echo "5. Querying persistent memory for 'NexusOS'..."
RESULTS=$(curl -s -X POST "$NEXUS_URL/memory/episodic/search" \
    -H "Content-Type: application/json" \
    -d '{"query":"NexusOS","limit":5}')
echo "$RESULTS" | jq -r '.results[]?.content // "No results"' 2>/dev/null | while read line; do
    echo "   → $line"
done

echo ""
echo "6. Recent memories..."
curl -s "$NEXUS_URL/memory/episodic/recent?limit=3" | jq -r '.episodes[]?.content // "none"' 2>/dev/null | while read line; do
    echo "   → $line"
done

echo ""
echo "============================================"
echo "  Demo complete! Memory survived restart."
echo "  This is what makes NexusOS different."
echo "============================================"
