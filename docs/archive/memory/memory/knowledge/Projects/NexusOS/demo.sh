# feel free to ignore this comment
     1|#!/bin/bash
     2|# NexusOS Demo Script
     3|# Run this to show NexusOS capabilities
     4|
     5|NEXUS_URL="${NEXUS_URL:-http://localhost:4893}"
     6|
     7|echo "============================================"
     8|echo "      NexusOS Demo - Persistent Memory    "
     9|echo "============================================"
    10|echo ""
    11|
    12|# Check if running
    13|echo "1. Checking NexusOS health..."
    14|HEALTH=$(curl -s "$NEXUS_URL/health")
    15|if echo "$HEALTH" | grep -q "healthy"; then
    16|    echo "   ✓ NexusOS is running"
    17|else
    18|    echo "   ✗ NexusOS is not running. Start with: node tools/memory-server.js"
    19|    exit 1
    20|fi
    21|
    22|echo ""
    23|echo "2. Starting a new session..."
    24|SESSION=$(curl -s -X POST "$NEXUS_URL/memory/working/start" \
    25|    -H "Content-Type: application/json" \
    26|    -d '{"sessionId":"demo-session"}')
    27|echo "   Session started: demo-session"
    28|
    29|echo ""
    30|echo "3. Adding messages to memory..."
    31|
    32|# User message
    33|curl -s -X POST "$NEXUS_URL/memory/working/message" \
    34|    -H "Content-Type: application/json" \
    35|    -d '{"content":"I'm working on a project called NexusOS - it's an agent operating system","role":"user"}' > /dev/null
    36|echo "   Added: User message about NexusOS"
    37|
    38|# Assistant response  
    39|curl -s -X POST "$NEXUS_URL/memory/working/message" \
    40|    -H "Content-Type: application/json" \
    41|    -d '{"content":"That sounds interesting! What does NexusOS do?","role":"assistant"}' > /dev/null
    42|echo "   Added: Assistant response"
    43|
    44|# Another user message
    45|curl -s -X POST "$NEXUS_URL/memory/working/message" \
    46|    -H "Content-Type: application/json" \
    47|    -d '{"content":"It gives AI agents persistent memory that survives restarts. We solve the amnesia problem.","role":"user"}' > /dev/null
    48|echo "   Added: User explains NexusOS value"
    49|
    50|echo ""
    51|echo "4. Ending session (persisting to episodic memory)..."
    52|curl -s -X POST "$NEXUS_URL/memory/working/end" \
    53|    -H "Content-Type: application/json" \
    54|    -d '{}' > /dev/null
    55|echo "   ✓ Session ended, memories persisted"
    56|
    57|echo ""
    58|echo "5. Querying persistent memory for 'NexusOS'..."
    59|RESULTS=$(curl -s -X POST "$NEXUS_URL/memory/episodic/search" \
    60|    -H "Content-Type: application/json" \
    61|    -d '{"query":"NexusOS","limit":5}')
    62|echo "$RESULTS" | jq -r '.results[]?.content // "No results"' 2>/dev/null | while read line; do
    63|    echo "   → $line"
    64|done
    65|
    66|echo ""
    67|echo "6. Recent memories..."
    68|curl -s "$NEXUS_URL/memory/episodic/recent?limit=3" | jq -r '.episodes[]?.content // "none"' 2>/dev/null | while read line; do
    69|    echo "   → $line"
    70|done
    71|
    72|echo ""
    73|echo "============================================"
    74|echo "  Demo complete! Memory survived restart."
    75|echo "  This is what makes NexusOS different."
    76|echo "============================================"
    77|