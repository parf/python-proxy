"""Command-line interface for python-proxy.

Copyright (C) 2025 Sergey Porfiriev <parf@difive.com>

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""

import argparse
import asyncio
import logging
import sys

from python_proxy.config import Config
from python_proxy.hooks import HookManager
from python_proxy.proxy import ProxyServer


def setup_logging(level: str):
    """Set up logging configuration.

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Python Proxy - Transparent HTTP proxy with modification hooks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start proxy on default port 8080
  python-proxy

  # Start with custom host and port
  python-proxy --host 127.0.0.1 --port 3128

  # Start with target host and hooks directory
  python-proxy --target http://example.com --hooks ./my-hooks

  # Load configuration from file
  python-proxy --config config.yaml

  # Use environment variables
  export PROXY_PORT=8080
  export PROXY_TARGET=http://example.com
  python-proxy
        """,
    )

    parser.add_argument(
        "--host",
        type=str,
        help="Host to bind the proxy server to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Port to bind the proxy server to (default: 8080)",
    )
    parser.add_argument(
        "--target",
        type=str,
        help="Default target host for proxying (e.g., http://example.com)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        help="Request timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--hooks",
        type=str,
        help="Directory containing hook modules",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Load configuration
    if args.config:
        try:
            config = Config.from_file(args.config)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        config = Config.from_env()

    # Override with CLI arguments
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    if args.target:
        config.target_host = args.target
    if args.timeout:
        config.timeout = args.timeout
    if args.hooks:
        config.hooks_dir = args.hooks
    if args.log_level:
        config.log_level = args.log_level

    # Set up logging
    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)

    # Load hooks
    hook_manager = HookManager(config.hooks_dir, config.hook_mappings)
    hook_manager.load_hooks()

    # Create proxy server
    # Set hooks if there are any (file-based or configuration-based)
    has_before_hooks = (
        hook_manager.before_request_hooks or hook_manager.pre_hook_configs
    )
    has_after_hooks = (
        hook_manager.after_response_hooks or hook_manager.post_hook_configs
    )

    before_hook = hook_manager.execute_before_request if has_before_hooks else None
    after_hook = hook_manager.execute_after_response if has_after_hooks else None
    proxy = ProxyServer(
        host=config.host,
        port=config.port,
        target_host=config.target_host,
        timeout=config.timeout,
        before_request_hook=before_hook,
        after_response_hook=after_hook,
    )

    # Run server
    logger.info("Starting Python Proxy Server")
    logger.info(f"Configuration: {config.to_dict()}")

    # Check if binding to privileged port
    if config.port < 1024:
        logger.warning(
            f"Attempting to bind to privileged port {config.port}. "
            "This may require elevated permissions."
        )

    try:
        asyncio.run(proxy.run())
    except PermissionError as e:
        if config.port < 1024:
            print(
                f"\n❌ Error: Cannot bind to port {config.port} - Permission denied\n",
                file=sys.stderr,
            )
            print("Privileged ports (below 1024) require special permissions.\n", file=sys.stderr)
            print("Quick setup (recommended):", file=sys.stderr)
            print("  ./scripts/install_wrapper.sh", file=sys.stderr)
            print("\nOther solutions:", file=sys.stderr)
            print(f"  1. Run with sudo: sudo python-proxy --port {config.port}", file=sys.stderr)
            print("  2. Grant Python permission to bind low ports:", file=sys.stderr)
            print(
                "     sudo setcap 'cap_net_bind_service=+ep' "
                "$(readlink -f $(which python3))",
                file=sys.stderr,
            )
            print("  3. Use a non-privileged port: python-proxy --port 8080", file=sys.stderr)
            print(
                "  4. Use port forwarding: sudo iptables -t nat -A PREROUTING "
                "-p tcp --dport 80 -j REDIRECT --to-port 8080",
                file=sys.stderr,
            )
            print(
                "\nSee examples/port80_setup.md for detailed instructions.\n", file=sys.stderr
            )
        else:
            logger.error(f"Permission error: {e}", exc_info=True)
        sys.exit(1)
    except OSError as e:
        if "Address already in use" in str(e):
            print(
                f"\n❌ Error: Port {config.port} is already in use\n", file=sys.stderr
            )
            print("Solutions:", file=sys.stderr)
            print(f"  1. Stop the service using port {config.port}", file=sys.stderr)
            print("  2. Use a different port: python-proxy --port 8081", file=sys.stderr)
            print(
                f"  3. Find what's using the port: sudo lsof -i :{config.port}\n",
                file=sys.stderr,
            )
        else:
            logger.error(f"OS error: {e}", exc_info=True)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
