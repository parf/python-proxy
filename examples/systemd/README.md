# Systemd Service Configuration

This directory contains example systemd service files for running python-proxy as a system service.

## Files

- `python-proxy.service` - Basic service file
- `python-proxy-with-socket.socket` - Socket activation (recommended for port 80)
- `python-proxy-hooks.service` - Service with hooks enabled

## Installation

### Method 1: Basic Service (Requires setcap)

This method requires setting up port 80 access first:

```bash
# 1. Run the setup script
./scripts/setup_port80.sh

# 2. Create proxy user
sudo useradd -r -s /bin/false proxy

# 3. Copy service file
sudo cp examples/systemd/python-proxy.service /etc/systemd/system/

# 4. Edit the service file to match your setup
sudo nano /etc/systemd/system/python-proxy.service

# 5. Reload systemd
sudo systemctl daemon-reload

# 6. Enable and start
sudo systemctl enable python-proxy
sudo systemctl start python-proxy

# 7. Check status
sudo systemctl status python-proxy
```

### Method 2: Socket Activation (Recommended for Port 80)

Socket activation allows systemd to bind the port (as root) and pass it to the service (running as regular user):

```bash
# 1. Create proxy user
sudo useradd -r -s /bin/false proxy

# 2. Copy service files
sudo cp examples/systemd/python-proxy.service /etc/systemd/system/
sudo cp examples/systemd/python-proxy-with-socket.socket /etc/systemd/system/

# 3. Edit files to match your setup
sudo nano /etc/systemd/system/python-proxy-with-socket.socket
sudo nano /etc/systemd/system/python-proxy.service

# 4. Reload systemd
sudo systemctl daemon-reload

# 5. Enable and start socket (not the service directly)
sudo systemctl enable python-proxy-with-socket.socket
sudo systemctl start python-proxy-with-socket.socket

# 6. The service will start automatically when a connection arrives
sudo systemctl status python-proxy-with-socket.socket
sudo systemctl status python-proxy.service
```

## Configuration

### Edit Service File

```bash
sudo systemctl edit python-proxy
```

This creates an override file in `/etc/systemd/system/python-proxy.service.d/override.conf`

Example override:

```ini
[Service]
# Change the port
ExecStart=
ExecStart=/usr/bin/python3 -m python_proxy.cli --host 192.168.2.7 --port 80 --target http://example.com

# Add environment variables
Environment="PROXY_HOOKS_DIR=/etc/python-proxy/hooks"
Environment="PROXY_LOG_LEVEL=DEBUG"
```

### Using Configuration File

```bash
# Create config directory
sudo mkdir -p /etc/python-proxy

# Create config file
sudo nano /etc/python-proxy/config.yaml
```

Content:
```yaml
host: "192.168.2.7"
port: 80
target_host: "http://example.com"
timeout: 30
hooks_dir: "/etc/python-proxy/hooks"
log_level: "INFO"
```

Update service file:
```ini
[Service]
ExecStart=/usr/bin/python3 -m python_proxy.cli --config /etc/python-proxy/config.yaml
```

## Managing the Service

```bash
# Start
sudo systemctl start python-proxy

# Stop
sudo systemctl stop python-proxy

# Restart
sudo systemctl restart python-proxy

# Enable on boot
sudo systemctl enable python-proxy

# Disable on boot
sudo systemctl disable python-proxy

# Check status
sudo systemctl status python-proxy

# View logs
sudo journalctl -u python-proxy -f

# View logs since boot
sudo journalctl -u python-proxy -b

# View logs from last hour
sudo journalctl -u python-proxy --since "1 hour ago"
```

## Troubleshooting

### Service fails to start

```bash
# Check detailed status
sudo systemctl status python-proxy -l

# View logs
sudo journalctl -u python-proxy -n 50

# Check if port is already in use
sudo lsof -i :80
```

### Permission errors on port 80

If using Method 1 (basic service), ensure Python has the capability:

```bash
getcap /usr/bin/python3
# Should show: cap_net_bind_service=ep

# If not, run:
sudo setcap 'cap_net_bind_service=+ep' /usr/bin/python3
```

### Service not starting after Python upgrade

```bash
# Reapply capability
sudo setcap 'cap_net_bind_service=+ep' /usr/bin/python3

# Restart service
sudo systemctl restart python-proxy
```

## Security Notes

- The service runs as a dedicated `proxy` user (not root)
- Socket activation is more secure as systemd handles the privileged port
- Consider using firewall rules to restrict access
- Enable SSL/TLS for production use
- Review the security hardening options in the service file

## Example: Production Setup

```bash
# 1. Create dedicated user
sudo useradd -r -s /bin/false -d /var/lib/python-proxy proxy

# 2. Install python-proxy
sudo pip install python-proxy  # or from source

# 3. Create directories
sudo mkdir -p /etc/python-proxy/hooks
sudo mkdir -p /var/log/python-proxy
sudo chown proxy:proxy /var/log/python-proxy

# 4. Create configuration
sudo tee /etc/python-proxy/config.yaml << EOF
host: "0.0.0.0"
port: 80
timeout: 30
hooks_dir: "/etc/python-proxy/hooks"
log_level: "INFO"
EOF

# 5. Install systemd files
sudo cp examples/systemd/python-proxy.service /etc/systemd/system/
sudo cp examples/systemd/python-proxy-with-socket.socket /etc/systemd/system/

# 6. Grant capability
sudo setcap 'cap_net_bind_service=+ep' /usr/bin/python3

# 7. Enable and start
sudo systemctl daemon-reload
sudo systemctl enable python-proxy-with-socket.socket
sudo systemctl start python-proxy-with-socket.socket

# 8. Verify
sudo systemctl status python-proxy-with-socket.socket
curl -x http://localhost:80 http://example.com/
```
