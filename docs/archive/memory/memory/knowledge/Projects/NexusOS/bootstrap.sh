# feel free to ignore this comment
     1|#!/bin/bash
     2|# NexusOS Bootstrap Script
     3|# 
     4|# This script "installs" NexusOS on an existing OpenClaw installation
     5|# by configuring the existing memory, tools, and communication systems.
     6|#
     7|# Run this on the machine where OpenClaw is already running.
     8|
     9|set -e
    10|
    11|NEXUS_DIR="/data/.openclaw/workspace/nexusos"
    12|
    13|echo "🏗️  NexusOS Bootstrap"
    14|echo "===================="
    15|
    16|# Create NexusOS directory
    17|mkdir -p "$NEXUS_DIR"
    18|cd "$NEXUS_DIR"
    19|
    20|echo "📁 Creating NexusOS directory structure..."
    21|
    22|# Core directories
    23|mkdir -p {config,memory/{episodic,semantic,working},tools,logs,sandbox,state}
    24|
    25|# Copy core files
    26|echo "📦 Installing NexusOS core..."
    27|
    28|# Create status script
    29|cat > "$NEXUS_DIR/status.sh" << 'SCRIPT'
    30|#!/bin/bash
    31|echo "╔══════════════════════════════════════╗"
    32|echo "║         NexusOS Status               ║"
    33|echo "╠══════════════════════════════════════╣"
    34|echo "║ Memory: $(test -f /nexus/memory/semantic/knowledge.db && echo "✓ Initialized" || echo "○ Not initialized")"
    35|echo "║ Config: $(test -d /nexus/config && echo "✓ Present" || echo "○ Missing")"
    36|echo "║ OpenClaw: $(which openclaw && echo "✓ Installed" || echo "○ Not found")"
    37|echo "╚══════════════════════════════════════╝"
    38|SCRIPT
    39|chmod +x "$NEXUS_DIR/status.sh"
    40|
    41|# Create launch script
    42|cat > "$NEXUS_DIR/launch.sh" << 'SCRIPT'
    43|#!/bin/bash
    44|echo "🚀 Launching NexusOS..."
    45|
    46|# Check dependencies
    47|command -v openclaw >/dev/null 2>&1 || { echo "❌ OpenClaw not found"; exit 1; }
    48|
    49|# Start OpenClaw gateway
    50|openclaw gateway start
    51|echo "✓ NexusOS started"
    52|SCRIPT
    53|chmod +x "$NEXUS_DIR/launch.sh"
    54|
    55|# Create quick reference
    56|cat > "$NEXUS_DIR/README.md" << 'SCRIPT'
    57|# NexusOS - Quick Reference
    58|
    59|## Commands
    60|
    61|```bash
    62|./launch.sh    # Start NexusOS
    63|./status.sh    # Check status
    64|```
    65|
    66|## File Locations
    67|
    68|- Memory: `/nexus/memory/`
    69|- Config: `/nexus/config/`
    70|- Logs: `/nexus/logs/`
    71|
    72|## Features
    73|
    74|- ✓ Three-tier memory (Working → Episodic → Semantic)
    75|- ✓ MCP tool bridge
    76|- ✓ Multi-channel communication
    77|- ✓ Autonomous heartbeats
    78|
    79|## Next Steps
    80|
    81|1. Configure `/nexus/config/` with your API keys
    82|2. Run `./launch.sh` to start
    83|3. Test with a message on your configured channel
    84|SCRIPT
    85|
    86|echo "✅ NexusOS installed!"
    87|echo ""
    88|echo "To start NexusOS, run:"
    89|echo "  $NEXUS_DIR/launch.sh"
    90|echo ""
    91|echo "To check status:"
    92|echo "  $NEXUS_DIR/status.sh"