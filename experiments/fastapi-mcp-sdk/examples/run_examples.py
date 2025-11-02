#!/usr/bin/env python3
"""
Shopping Cart MCP Examples Runner
This script provides an easy way to run different MCP server examples.
"""

import anyio
import argparse
import sys


def print_banner():
    """Print the banner."""
    print("Shopping Cart MCP Server Examples")


def print_usage():
    """Print usage information."""
    print("\n📋 Available Examples:")
    print("  1. fastmcp     - Method 1: FastMCP.from_fastapi (separate servers)")
    print("  2. mount       - Method 2: FastAPIMCPServer mount (integrated)")
    print("  3. fastapi     - FastAPI only (no MCP)")
    print("\n🚀 Usage:")
    print("  python run_examples.py <method>")
    print("\n📖 Examples:")
    print("  python run_examples.py fastmcp                  # Run with separate servers")
    print("  python run_examples.py mount                    # Run with integrated server")
    print("  python run_examples.py fastapi                  # Run FastAPI only")


async def run_fastmcp():
    """Run FastMCP example."""
    from _run_with_fastmcp import main

    await main()


async def run_mount():
    """Run mount example."""
    from _run_with_mount import main

    await main()


async def run_fastapi_only():
    """Run FastAPI only."""
    import uvicorn

    # Import the configured app
    from _shopping_cart_app import app

    config = uvicorn.Config(app=app, host="127.0.0.1", port=8000, log_level="info", reload=False)

    print("Server running: http://127.0.0.1:8000/docs")
    print("Press Ctrl+C to stop")
    server = uvicorn.Server(config)
    await server.serve()


def main():
    """Main function."""
    print_banner()

    parser = argparse.ArgumentParser(
        description="Run Shopping Cart MCP Server Examples",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "method",
        choices=["fastmcp", "mount", "fastapi"],
        help="Method to run (fastmcp, mount, or fastapi)",
    )

    args = parser.parse_args()

    if args.method == "fastmcp":
        anyio.run(run_fastmcp)
    elif args.method == "mount":
        anyio.run(run_mount)
    elif args.method == "fastapi":
        anyio.run(run_fastapi_only)
    else:
        print(f"❌ Unknown method: {args.method}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
