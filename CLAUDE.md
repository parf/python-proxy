# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

python-proxy is a transparent Python-based HTTP proxy server (similar to nginx) with powerful request/response modification hooks. It uses async/await architecture built on `aiohttp` for high-performance HTTP proxying.

## Architecture

### Core Components

1. **ProxyServer** (`python_proxy/proxy.py`): Main async HTTP proxy server
   - Handles incoming requests and forwards to target servers
   - Manages request/response lifecycle
   - Executes hooks at appropriate stages
   - Built on `aiohttp.web` for server and `aiohttp.ClientSession` for outgoing requests

2. **HookManager** (`python_proxy/hooks.py`): Hook system for request/response modification
   - Discovers and loads hook modules from a directory
   - Executes `before_request` hooks before proxying
   - Executes `after_response` hooks after receiving response
   - Supports both function naming convention and decorator-based registration

3. **Config** (`python_proxy/config.py`): Configuration management
   - Supports loading from YAML files, environment variables, and CLI arguments
   - Priority: CLI args > config file > env vars > defaults

4. **CLI** (`python_proxy/cli.py`): Command-line interface entry point

### Request Flow

1. Client sends request to proxy server
2. Proxy receives request via `handle_request()`
3. Check for `.local` domain suffix and strip if present (e.g., `example.com.local:8080` → `example.com:80`)
4. Target URL determined from headers or config (priority order):
   - `X-Proxy-Server` header (host or host:port)
   - `X-Proxy-Target` header (full URL, legacy)
   - Auto-detected from `.local` domain stripping
   - Default `target_host` from configuration
5. Host header override applied if `X-Proxy-Host` is present
6. `before_request` hooks execute (can modify method, URL, headers, body)
7. Modified request forwarded to target server
8. Response received from target
9. `after_response` hooks execute (can modify response body)
10. Modified response returned to client

### Hook System

Hooks are Python files in a designated directory. Two types:

- **before_request hooks**: `async def before_request(request, request_data) -> dict`
  - Modify request before proxying
  - `request_data` contains: method, url, headers, data

- **after_response hooks**: `async def after_response(response, body) -> bytes`
  - Modify response after receiving from target
  - Can inspect response headers/status via `response` object

Hooks can be registered via:
1. Function name (`before_request` or `after_response`)
2. Decorator (`@before_request` or `@after_response`)

## Development Commands

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Install with dev dependencies
pip install -r requirements-dev.txt

# Install in editable mode
pip install -e .
```

### Running

```bash
# Run proxy with default settings (port 8080)
python-proxy

# Run with custom configuration
python-proxy --port 3128 --target http://example.com

# Run with hooks
python-proxy --hooks ./hooks --target http://example.com

# Run from config file
python-proxy --config examples/config.yaml

# Run module directly (for development)
python -m python_proxy.cli
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=python_proxy --cov-report=term-missing

# Run specific test file
pytest tests/test_config.py

# Run specific test
pytest tests/test_config.py::test_config_defaults

# Run with verbose output
pytest -v

# Run with print statements visible
pytest -s
```

### Linting

```bash
# Check code with ruff
ruff check .

# Auto-fix issues
ruff check --fix .

# Check specific file
ruff check python_proxy/proxy.py
```

## Project Structure

```
python-proxy/
├── python_proxy/          # Main package
│   ├── __init__.py
│   ├── proxy.py          # ProxyServer class
│   ├── hooks.py          # HookManager and decorators
│   ├── config.py         # Configuration handling
│   └── cli.py            # CLI entry point
├── tests/                # Test suite
│   ├── test_proxy.py
│   ├── test_hooks.py
│   └── test_config.py
├── examples/             # Example hooks and configs
│   ├── example_hooks.py  # Simple hook examples
│   ├── advanced_hooks.py # Advanced hook patterns
│   └── config.yaml       # Example configuration
├── hooks/                # Default hooks directory (create as needed)
├── pyproject.toml        # Project metadata and dependencies
├── requirements.txt      # Runtime dependencies
└── requirements-dev.txt  # Development dependencies
```

## Key Design Patterns

### Async Throughout
All I/O operations are async. Use `async def` and `await` for any function that does network I/O or calls other async functions.

### Hook Isolation
Each hook executes independently. Exceptions in one hook don't stop others from executing. Errors are logged but the proxy continues operating.

### Flexible Targeting
Requests can be routed to different targets via (in priority order):
1. **X-Proxy-Server** header: Simple `host` or `host:port` format
   - Port defaults to 80 (http)
   - Port 443 automatically uses https
   - Examples: `example.com`, `example.com:8080`, `192.168.1.100:3000`
2. **X-Proxy-Target** header: Full URL with scheme (legacy support)
   - Example: `http://example.com:8080`
3. **Automatic .local domain stripping**: If no explicit headers are present
   - `example.com.local` → `example.com:80`
   - `api.service.local:8080` → `api.service:80` (port ignored, defaults to 80)
   - Always routes to port 80 (HTTP), regardless of port in .local request
   - Useful for /etc/hosts-based testing and local development
4. **Default target_host** from configuration

### Host Header Override
The **X-Proxy-Host** header allows overriding the Host header sent to the backend:
- Useful for virtual hosting where backend expects specific hostname
- Example: Send request to `192.168.1.100:8080` but with `Host: myapp.example.com`

### Header Cleanup
The proxy automatically removes proxy control headers (`X-Proxy-Server`, `X-Proxy-Target`, `X-Proxy-Host`) and problematic headers (like `Transfer-Encoding`, `Content-Encoding`) that could cause issues when forwarding requests.

## Configuration Options

| Option | Env Var | Default | Description |
|--------|---------|---------|-------------|
| host | PROXY_HOST | 0.0.0.0 | Bind address |
| port | PROXY_PORT | 8080 | Bind port (see below for port 80) |
| target_host | PROXY_TARGET | None | Default target |
| timeout | PROXY_TIMEOUT | 30 | Request timeout (seconds) |
| hooks_dir | PROXY_HOOKS_DIR | None | Hooks directory |
| log_level | PROXY_LOG_LEVEL | INFO | Logging level |

### Running on Port 80 (Privileged Ports)

Ports below 1024 require special permissions. The CLI automatically detects this and provides helpful error messages with solutions.

**Quick setup:**
```bash
# Run the setup script
./scripts/setup_port80.sh

# Or manually grant capability
sudo setcap 'cap_net_bind_service=+ep' $(which python3)
```

**Alternative approaches:**
- Run with sudo (not recommended)
- Use iptables port forwarding
- Use systemd socket activation (best for production)

See `examples/port80_setup.md` for detailed instructions.

## Common Development Tasks

### Adding a New Hook Type
1. Add hook list to `HookManager.__init__()`
2. Add discovery logic to `HookManager._load_hook_file()`
3. Add execution method to `HookManager`
4. Update `ProxyServer` to call the execution method at the right point
5. Add tests for the new hook type

### Modifying Request Flow
The main request flow is in `ProxyServer.handle_request()`. Key steps:
1. Determine target URL
2. Build request data dict
3. Execute before_request hooks
4. Forward request with `self.session.request()`
5. Execute after_response hooks
6. Return response

### Testing Hooks
Create a test hook file in a temp directory, use `HookManager` to load it, then verify hooks are registered and execute correctly. See `tests/test_hooks.py` for patterns.

## License

This project is licensed under GPL v2.
