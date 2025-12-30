# Running on Port 80 Without Root

This guide explains how to run python-proxy on port 80 (or any privileged port below 1024) without requiring root privileges.

## The Problem

On Linux/Unix systems, ports below 1024 (privileged ports) require root privileges to bind. This is a security measure to prevent unprivileged users from running services on standard ports like HTTP (80), HTTPS (443), etc.

## Solutions

### Option 1: Using setcap (Recommended)

Grant the Python binary the capability to bind to privileged ports. This is a one-time setup per Python installation.

```bash
# Find your Python executable
which python3
# Example output: /usr/bin/python3

# Resolve symlinks and grant the capability (important!)
sudo setcap 'cap_net_bind_service=+ep' $(readlink -f $(which python3))

# Verify the capability was set
getcap $(readlink -f $(which python3))
# Should output: /usr/bin/python3.13 cap_net_bind_service=ep (or similar)

# Now you can run without sudo
python-proxy --host 192.168.2.7 --port 80
```

**Important:** Many systems have `/usr/bin/python3` as a symlink to the actual binary (e.g., `python3.13`). The `setcap` command requires the actual file, not the symlink, so we use `readlink -f` to resolve it. See the [Symlink issues](#symlink-issues-invalid-file-for-capability-operation) section below for details.

**Advantages:**
- One-time setup
- No need to run as root
- Works for all Python scripts

**Considerations:**
- Applies to all Python scripts run with this binary
- Needs to be reapplied after Python upgrades
- If using virtual environments, apply to the venv's Python binary

#### Virtual Environment Setup

```bash
# Activate your virtual environment
source venv/bin/activate

# Find the venv's Python (resolve symlinks)
VENV_PYTHON=$(readlink -f $(which python))
echo "Virtual environment Python: $VENV_PYTHON"

# Grant capability to venv's Python
sudo setcap 'cap_net_bind_service=+ep' "$VENV_PYTHON"

# Run proxy
python-proxy --port 80
```

### Option 2: Run with sudo

The simplest but least secure option.

```bash
# Run as root
sudo python-proxy --host 192.168.2.7 --port 80

# Or with specific user after binding
sudo -u youruser python-proxy --port 80
```

**Advantages:**
- Simple, no setup required
- Works immediately

**Disadvantages:**
- Runs entire process as root (security risk)
- Not recommended for production

### Option 3: Port Forwarding with iptables

Bind to a high port (e.g., 8080) and use iptables to redirect traffic from port 80.

```bash
# Start proxy on high port
python-proxy --host 0.0.0.0 --port 8080

# In another terminal, set up port forwarding
sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080

# For external access, also add:
sudo iptables -t nat -A OUTPUT -p tcp -d localhost --dport 80 -j REDIRECT --to-port 8080
```

**Make iptables rules persistent:**

```bash
# On Debian/Ubuntu
sudo apt-get install iptables-persistent
sudo netfilter-persistent save

# On RHEL/CentOS/Fedora
sudo service iptables save
```

**Remove the rule later:**
```bash
sudo iptables -t nat -D PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080
sudo iptables -t nat -D OUTPUT -p tcp -d localhost --dport 80 -j REDIRECT --to-port 8080
```

**Advantages:**
- Proxy runs as regular user
- Can be used for any port mapping
- No changes to Python binary

**Disadvantages:**
- Requires root for iptables rules
- More complex to set up
- Rules need to be persistent across reboots

### Option 4: Using authbind

`authbind` allows specific users to bind to specific privileged ports.

```bash
# Install authbind
sudo apt-get install authbind  # Debian/Ubuntu
sudo yum install authbind      # RHEL/CentOS

# Allow current user to bind to port 80
sudo touch /etc/authbind/byport/80
sudo chmod 500 /etc/authbind/byport/80
sudo chown $USER /etc/authbind/byport/80

# Run with authbind
authbind --deep python-proxy --host 192.168.2.7 --port 80
```

**Advantages:**
- Fine-grained control per port
- Doesn't affect other Python scripts
- Secure

**Disadvantages:**
- Requires installation
- Extra command prefix needed

### Option 5: Systemd Socket Activation

Let systemd bind the socket and pass it to the application.

Create `/etc/systemd/system/python-proxy.socket`:

```ini
[Unit]
Description=Python Proxy Socket

[Socket]
ListenStream=192.168.2.7:80
Accept=false

[Install]
WantedBy=sockets.target
```

Create `/etc/systemd/system/python-proxy.service`:

```ini
[Unit]
Description=Python Proxy Server
Requires=python-proxy.socket

[Service]
Type=simple
User=youruser
Group=yourgroup
WorkingDirectory=/path/to/python-proxy
ExecStart=/usr/bin/python3 -m python_proxy.cli --host 192.168.2.7 --port 80
StandardOutput=journal
StandardError=journal
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable python-proxy.socket
sudo systemctl start python-proxy.socket
sudo systemctl start python-proxy.service
```

**Advantages:**
- Professional production setup
- Proper service management
- Socket bound by systemd (as root)
- Service runs as regular user
- Automatic restarts

**Disadvantages:**
- More complex initial setup
- Requires systemd

## Quick Setup Script

Create `setup_port80.sh`:

```bash
#!/bin/bash
set -e

echo "Setting up python-proxy for port 80 access..."
echo ""

# Find Python executable
PYTHON_BIN=$(which python3)
echo "Python binary: $PYTHON_BIN"

# Check if setcap is available
if ! command -v setcap &> /dev/null; then
    echo "Error: setcap not found. Please install libcap2-bin package."
    exit 1
fi

# Grant capability
echo "Granting cap_net_bind_service capability..."
sudo setcap 'cap_net_bind_service=+ep' "$PYTHON_BIN"

# Verify
echo ""
echo "Verification:"
getcap "$PYTHON_BIN"

echo ""
echo "✓ Setup complete! You can now run:"
echo "  python-proxy --host 192.168.2.7 --port 80"
echo ""
echo "Note: After upgrading Python, you'll need to run this script again."
```

Make it executable and run:

```bash
chmod +x setup_port80.sh
./setup_port80.sh
```

## Testing

```bash
# Test if port 80 works
python-proxy --host 0.0.0.0 --port 80 --target http://example.com

# In another terminal, test
curl -x http://localhost:80 http://example.com.local/

# Or test with a specific IP
python-proxy --host 192.168.2.7 --port 80
curl -x http://192.168.2.7:80 http://example.com/
```

## Troubleshooting

### "Permission denied" error

```bash
# Check if capability is set
getcap $(which python3)

# Should show: cap_net_bind_service=ep
# If not, run the setcap command again
```

### "Address already in use"

```bash
# Check what's using port 80
sudo lsof -i :80
sudo netstat -tlnp | grep :80

# Common culprits: Apache, Nginx, other web servers
# Stop the service or use a different port
```

### Capability not working after Python upgrade

```bash
# Reapply the capability (resolve symlinks)
sudo setcap 'cap_net_bind_service=+ep' $(readlink -f $(which python3))
```

### Virtual environment issues

```bash
# Apply capability to venv's Python, not system Python
source venv/bin/activate
sudo setcap 'cap_net_bind_service=+ep' $(readlink -f $(which python))
```

### Symlink issues: "Invalid file for capability operation"

If you get an error like `Invalid file 'setcap' for capability operation`, it's because `/usr/bin/python3` is a symlink to the actual Python binary (e.g., `python3.13`). The `setcap` command requires the actual file, not a symlink.

```bash
# Check if Python is a symlink
ls -la $(which python3)
# Example output: /usr/bin/python3 -> python3.13

# Resolve the symlink and apply capability to the actual binary
sudo setcap 'cap_net_bind_service=+ep' $(readlink -f $(which python3))

# Verify
getcap $(readlink -f $(which python3))
# Should show: /usr/bin/python3.13 cap_net_bind_service=ep
```

**Note:** The provided setup scripts (`setup_port80.sh` and `install_wrapper.sh`) automatically resolve symlinks for you.

## Security Considerations

- **setcap**: Least privilege - only grants network binding capability
- **sudo**: Most dangerous - entire process runs as root
- **iptables**: Good middle ground - proxy runs as user, but requires root for firewall rules
- **authbind**: Fine-grained control, but requires installation
- **systemd**: Best for production - proper service management with user separation

## Recommended Approach

**Development:** Use setcap or high port with iptables
**Production:** Use systemd socket activation or setcap with proper user

## Production Example

```bash
# 1. Set up dedicated user
sudo useradd -r -s /bin/false proxy

# 2. Install proxy
sudo pip install -e /path/to/python-proxy

# 3. Grant capability (resolve symlinks)
sudo setcap 'cap_net_bind_service=+ep' $(readlink -f $(which python3))

# 4. Create systemd service (see Option 5 above)

# 5. Run as proxy user
sudo systemctl start python-proxy
```
