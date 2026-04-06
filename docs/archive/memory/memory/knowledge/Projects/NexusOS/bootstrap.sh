#!/bin/bash
# NexusOS Bootstrap Script
# 
# This script "installs" NexusOS on an existing OpenClaw installation
# by configuring the existing memory, tools, and communication systems.
#
# Run this on the machine where OpenClaw is already running.

set -e

NEXUS_DIR="/data/.openclaw/workspace/nexusos"

echo "🏗️  NexusOS Bootstrap"
echo "===================="

# Create NexusOS directory
mkdir -p "$NEXUS_DIR"
cd "$NEXUS_DIR"

echo "📁 Creating NexusOS directory structure..."

# Core directories
mkdir -p {config,memory/{episodic,semantic,working},tools,logs,sandbox,state}

# Copy core files
echo "📦 Installing NexusOS core..."

# Create status script
cat > "$NEXUS_DIR/status.sh" << 'SCRIPT'
#!/bin/bash
echo "╔══════════════════════════════════════╗"
echo "║         NexusOS Status               ║"
echo "╠══════════════════════════════════════╣"
echo "║ Memory: $(test -f /nexus/memory/semantic/knowledge.db && echo "✓ Initialized" || echo "○ Not initialized")"
echo "║ Config: $(test -d /nexus/config && echo "✓ Present" || echo "○ Missing")"
echo "║ OpenClaw: $(which openclaw && echo "✓ Installed" || echo "○ Not found")"
echo "╚══════════════════════════════════════╝"
SCRIPT
chmod +x "$NEXUS_DIR/status.sh"

# Create launch script
cat > "$NEXUS_DIR/launch.sh" << 'SCRIPT'
#!/bin/bash
echo "🚀 Launching NexusOS..."

# Check dependencies
command -v openclaw >/dev/null 2>&1 || { echo "❌ OpenClaw not found"; exit 1; }

# Start OpenClaw gateway
openclaw gateway start
echo "✓ NexusOS started"
SCRIPT
chmod +x "$NEXUS_DIR/launch.sh"

# Create quick reference
cat > "$NEXUS_DIR/README.md" << 'SCRIPT'
# NexusOS - Quick Reference

## Commands

```bash
./launch.sh    # Start NexusOS
./status.sh    # Check status
```

## File Locations

- Memory: `/nexus/memory/`
- Config: `/nexus/config/`
- Logs: `/nexus/logs/`

## Features

- ✓ Three-tier memory (Working → Episodic → Semantic)
- ✓ MCP tool bridge
- ✓ Multi-channel communication
- ✓ Autonomous heartbeats

## Next Steps

1. Configure `/nexus/config/` with your API keys
2. Run `./launch.sh` to start
3. Test with a message on your configured channel
SCRIPT

echo "✅ NexusOS installed!"
echo ""
echo "To start NexusOS, run:"
echo "  $NEXUS_DIR/launch.sh"
echo ""
echo "To check status:"
echo "  $NEXUS_DIR/status.sh"