#!/bin/bash
# Install python-proxy wrapper for convenient port 80 access

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Python Proxy - Wrapper Installation                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Determine installation directory
if [ -w "/usr/local/bin" ]; then
    INSTALL_DIR="/usr/local/bin"
else
    INSTALL_DIR="$HOME/.local/bin"
    mkdir -p "$INSTALL_DIR"
fi

WRAPPER="$INSTALL_DIR/python-proxy"

echo "📦 Installing wrapper to: $WRAPPER"

# Create wrapper script
cat > "$WRAPPER" << 'EOF'
#!/bin/bash
# Python Proxy wrapper script
# Automatically installed by install_wrapper.sh

# Find Python (prefer python3)
PYTHON="${PYTHON:-python3}"

# Run python-proxy with all arguments
exec "$PYTHON" -m python_proxy.cli "$@"
EOF

chmod +x "$WRAPPER"

echo "✅ Wrapper installed successfully!"
echo ""

# Set up capability on Python
PYTHON_BIN=$(which python3)
echo "🔧 Setting up port 80 capability on Python..."
echo "   Python: $PYTHON_BIN"

# Resolve symlinks to get the actual binary
# setcap requires the actual file, not a symlink
PYTHON_RESOLVED=$(readlink -f "$PYTHON_BIN")
if [ -z "$PYTHON_RESOLVED" ] || [ ! -f "$PYTHON_RESOLVED" ]; then
    echo "⚠️  Could not resolve Python binary path"
    echo "   You may need to run manually:"
    echo "   sudo setcap 'cap_net_bind_service=+ep' \$(readlink -f \$(which python3))"
else
    if [ "$PYTHON_BIN" != "$PYTHON_RESOLVED" ]; then
        echo "   Resolved symlink: $PYTHON_BIN -> $PYTHON_RESOLVED"
        PYTHON_BIN="$PYTHON_RESOLVED"
    fi
fi

echo ""

if sudo setcap 'cap_net_bind_service=+ep' "$PYTHON_BIN"; then
    echo "✅ Capability granted!"
else
    echo "⚠️  Could not set capability. You may need to run:"
    echo "   sudo setcap 'cap_net_bind_service=+ep' $PYTHON_BIN"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ✅ Installation Complete!                                 ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Usage:"
echo "  python-proxy --host 192.168.2.7 --port 80"
echo "  python-proxy --port 80 --target http://example.com"
echo ""

if [ "$INSTALL_DIR" = "$HOME/.local/bin" ]; then
    echo "📝 Note: Make sure $HOME/.local/bin is in your PATH"
    if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
        echo ""
        echo "Add this to your ~/.bashrc or ~/.profile:"
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo ""
    fi
fi

echo "📚 For more options, see:"
echo "  examples/bash_wrapper_setup.md"
echo ""
