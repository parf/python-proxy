# Using Bash Wrapper with setcap

This guide explains different approaches to using bash scripts with capabilities for port 80 access.

## The Challenge

You **cannot** effectively set capabilities directly on bash scripts because:
1. Capabilities are set on the file itself
2. When you run a script, the interpreter (`/bin/bash`) executes, not the script file
3. The capability doesn't transfer to the interpreter

```bash
# This WON'T work as expected:
chmod +x my-script.sh
sudo setcap 'cap_net_bind_service=+ep' my-script.sh
./my-script.sh  # bash doesn't have the capability
```

## Solutions

### Option 1: Set Capability on Python (Recommended)

This is what we do by default - simplest and most secure:

```bash
# Use readlink -f to resolve symlinks (some systems have /usr/bin/python3 -> python3.13)
sudo setcap 'cap_net_bind_service=+ep' $(readlink -f $(which python3))
python-proxy --port 80
```

**Note:** If `/usr/bin/python3` is a symlink, setcap must be applied to the actual binary file, not the symlink. The command above automatically resolves this.

### Option 2: Set Capability on Bash Interpreter (NOT RECOMMENDED)

**Warning:** This gives ALL bash scripts the ability to bind to privileged ports!

```bash
# Not recommended - affects all bash scripts
sudo setcap 'cap_net_bind_service=+ep' /bin/bash

# Now any bash script can bind to port 80
./scripts/python-proxy-port80 --port 80
```

**Why this is dangerous:**
- Every bash script you run can now bind to privileged ports
- Security risk if you run untrusted scripts
- Only do this in controlled environments

**To remove:**
```bash
sudo setcap -r /bin/bash
```

### Option 3: Use a Compiled Wrapper (Recommended for Distribution)

Create a small C program wrapper that has capabilities:

Create `wrapper.c`:
```c
#include <unistd.h>
#include <stdio.h>

int main(int argc, char *argv[]) {
    // Build command
    char *args[argc + 3];
    args[0] = "python3";
    args[1] = "-m";
    args[2] = "python_proxy.cli";

    // Copy remaining arguments
    for (int i = 1; i < argc; i++) {
        args[i + 2] = argv[i];
    }
    args[argc + 2] = NULL;

    // Execute
    execvp("python3", args);
    perror("Failed to execute python3");
    return 1;
}
```

Compile and set capability:
```bash
gcc -o python-proxy-port80 wrapper.c
sudo setcap 'cap_net_bind_service=+ep' python-proxy-port80

# Now use it
./python-proxy-port80 --port 80
```

**Advantages:**
- Capability only applies to this specific wrapper
- Doesn't affect other scripts or Python programs
- Good for distribution

### Option 4: Use sudo with Bash Wrapper

Create a script that uses sudo only for the binding part:

```bash
#!/bin/bash
# scripts/python-proxy-sudo

# Check if we need sudo
if [ "$EUID" -ne 0 ] && [ "$1" = "--port" ] && [ "$2" -lt 1024 ]; then
    echo "Privileged port detected, using sudo..."
    exec sudo -E "$0" "$@"
fi

# Run python-proxy
exec python3 -m python_proxy.cli "$@"
```

**Usage:**
```bash
./scripts/python-proxy-sudo --port 80
# Will auto-sudo only when needed
```

### Option 5: Hybrid Approach - Setup Script with Wrapper

Combine both approaches for flexibility:

**Setup script** (`scripts/setup_bash_wrapper.sh`):
```bash
#!/bin/bash
set -e

echo "Setting up bash wrapper for port 80..."

# Create wrapper if it doesn't exist
WRAPPER="$HOME/.local/bin/python-proxy-port80"
mkdir -p "$HOME/.local/bin"

cat > "$WRAPPER" << 'EOF'
#!/bin/bash
exec python3 -m python_proxy.cli "$@"
EOF

chmod +x "$WRAPPER"

# Grant capability to Python (not bash)
PYTHON_BIN=$(readlink -f $(which python3))
echo "Granting capability to: $PYTHON_BIN"
sudo setcap 'cap_net_bind_service=+ep' "$PYTHON_BIN"

echo "✅ Setup complete!"
echo ""
echo "Usage:"
echo "  python-proxy-port80 --port 80"
echo "  # or"
echo "  $WRAPPER --port 80"
```

## Comparison Table

| Method | Security | Simplicity | Scope |
|--------|----------|------------|-------|
| setcap on Python | ✅ Good | ✅ Simple | All Python scripts |
| setcap on bash | ❌ Poor | ✅ Simple | ALL bash scripts |
| Compiled wrapper | ✅ Excellent | ⚠️ Complex | Only this wrapper |
| sudo wrapper | ⚠️ Moderate | ✅ Simple | Only when needed |
| Hybrid | ✅ Good | ✅ Simple | Python + convenience |

## Recommended Approach for Different Use Cases

### Development (Local Machine)
```bash
# Simple and effective (resolves symlinks)
sudo setcap 'cap_net_bind_service=+ep' $(readlink -f $(which python3))
python-proxy --port 80
```

### Production (Server)
```bash
# Use systemd with socket activation
# See examples/systemd/README.md
sudo systemctl start python-proxy.socket
```

### Distribution (Package)
```bash
# Include compiled wrapper
# Or provide setup script that sets capability on Python
```

### Shared Server (Multiple Users)
```bash
# Use per-user compiled wrapper
# Or use authbind
authbind --deep python-proxy --port 80
```

## Using the Provided Wrapper

We've included a bash wrapper at `scripts/python-proxy-port80`:

```bash
# Option 1: Set capability on Python (recommended, resolves symlinks)
sudo setcap 'cap_net_bind_service=+ep' $(readlink -f $(which python3))
./scripts/python-proxy-port80 --port 80

# Option 2: Set capability on bash (not recommended)
sudo setcap 'cap_net_bind_service=+ep' /bin/bash
./scripts/python-proxy-port80 --port 80
# Remember to remove: sudo setcap -r /bin/bash

# Option 3: Use with sudo
sudo ./scripts/python-proxy-port80 --port 80
```

## Testing

```bash
# Test if capability works
getcap $(which python3)
# Should show: cap_net_bind_service=ep

# Test the wrapper
./scripts/python-proxy-port80 --port 80 &
PID=$!

# Check if it's listening
sleep 1
sudo lsof -i :80 | grep python

# Clean up
kill $PID
```

## Troubleshooting

### Wrapper says "command not found"
```bash
# Make sure Python is in PATH
which python3

# Or specify full path in wrapper
sed -i 's/python3/\/usr\/bin\/python3/' scripts/python-proxy-port80
```

### Still getting permission denied
```bash
# Check Python capability
getcap $(which python3)

# Check if you're using the right Python
which python3
# Should match the one with capability

# If using venv:
source venv/bin/activate
sudo setcap 'cap_net_bind_service=+ep' $(which python)
```

### Capability lost after Python upgrade
```bash
# Reapply capability
sudo setcap 'cap_net_bind_service=+ep' $(which python3)
```

## Security Best Practices

1. ✅ **DO:** Set capability on specific Python binary
2. ✅ **DO:** Use compiled wrapper for distribution
3. ✅ **DO:** Use systemd socket activation in production
4. ❌ **DON'T:** Set capability on `/bin/bash`
5. ❌ **DON'T:** Run entire application as root
6. ❌ **DON'T:** Set multiple capabilities unnecessarily

## Conclusion

**For most use cases, setting the capability on Python is the best approach:**

```bash
# One-time setup (resolves symlinks automatically)
sudo setcap 'cap_net_bind_service=+ep' $(readlink -f $(which python3))

# Then use normally
python-proxy --port 80
# or
./scripts/python-proxy-port80 --port 80
```

**Important:** Use `readlink -f` to resolve symlinks. On many systems, `/usr/bin/python3` is a symlink to the actual binary (e.g., `python3.13`), and setcap requires the actual file, not the symlink.

The bash wrapper is just for convenience - the actual capability should be on the Python interpreter.
