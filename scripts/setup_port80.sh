#!/bin/bash
# Setup script to enable python-proxy to bind to port 80 without root

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Python Proxy - Port 80 Setup                             ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "⚠️  Warning: Please run this script as a regular user (not sudo)"
    echo "   The script will prompt for sudo when needed."
    exit 1
fi

# Find Python executable
echo "🔍 Finding Python executable..."
if [ -n "$VIRTUAL_ENV" ]; then
    PYTHON_BIN="$VIRTUAL_ENV/bin/python"
    echo "   Using virtual environment Python: $PYTHON_BIN"
else
    PYTHON_BIN=$(which python3)
    echo "   Using system Python: $PYTHON_BIN"
fi

if [ ! -e "$PYTHON_BIN" ]; then
    echo "❌ Error: Python binary not found at $PYTHON_BIN"
    exit 1
fi

# Resolve symlinks to get the actual binary
# setcap requires the actual file, not a symlink
PYTHON_RESOLVED=$(readlink -f "$PYTHON_BIN")
if [ -z "$PYTHON_RESOLVED" ] || [ ! -f "$PYTHON_RESOLVED" ]; then
    echo "❌ Error: Could not resolve Python binary path"
    echo "   Original: $PYTHON_BIN"
    exit 1
fi

if [ "$PYTHON_BIN" != "$PYTHON_RESOLVED" ]; then
    echo "   Resolved symlink: $PYTHON_BIN -> $PYTHON_RESOLVED"
    PYTHON_BIN="$PYTHON_RESOLVED"
fi

# Check if setcap is available
echo ""
echo "🔍 Checking for setcap..."
if ! command -v setcap &> /dev/null; then
    echo "❌ Error: setcap not found."
    echo ""
    echo "Please install the required package:"
    echo "  Ubuntu/Debian: sudo apt-get install libcap2-bin"
    echo "  RHEL/CentOS:   sudo yum install libcap"
    echo "  Fedora:        sudo dnf install libcap"
    exit 1
fi

# Check current capability
echo ""
echo "📋 Current capability status:"
CURRENT_CAP=$(getcap "$PYTHON_BIN" 2>/dev/null || echo "none")
echo "   $CURRENT_CAP"

# Grant capability
echo ""
echo "🔧 Granting cap_net_bind_service capability..."
echo "   This will prompt for your sudo password."
echo ""

if sudo setcap 'cap_net_bind_service=+ep' "$PYTHON_BIN"; then
    echo "✅ Capability granted successfully!"
else
    echo "❌ Failed to grant capability"
    exit 1
fi

# Verify
echo ""
echo "✓ Verification:"
NEW_CAP=$(getcap "$PYTHON_BIN")
echo "  $NEW_CAP"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ✅ Setup Complete!                                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "You can now run python-proxy on port 80 without sudo:"
echo "  python-proxy --host 192.168.2.7 --port 80"
echo "  python-proxy --host 0.0.0.0 --port 80"
echo ""
echo "📝 Notes:"
echo "  • This capability persists across reboots"
echo "  • You'll need to reapply after Python upgrades"
echo "  • For virtual environments, run this script with the venv activated"
echo ""
echo "📚 See examples/port80_setup.md for more options and troubleshooting"
echo ""
