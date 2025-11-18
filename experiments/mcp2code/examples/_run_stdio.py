"""
Shopping Cart MCP Server - stdio transport
This script runs the shopping cart MCP server using stdio transport.
It can be used as a command-line MCP server.
"""

import os
import sys
from pathlib import Path
import anyio
from fastmcp import FastMCP


# Enable experimental parser BEFORE importing FastMCP
os.environ["FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER"] = "true"

# Add current directory to path to import shopping cart app
# When run as module (python -m examples._run_stdio), __file__ is the .py file
# When run directly, __file__ is also the .py file
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))


def create_stdio_mcp_server():
    """Create MCP server using stdio transport."""
    # Import the configured app
    from _shopping_cart_app import app as shopping_cart_app

    # Define tags for the MCP server
    server_tags = {"shopping", "ecommerce", "cart", "orders", "products", "users"}

    # Create MCP server from FastAPI app
    mcp = FastMCP.from_fastapi(
        app=shopping_cart_app,
        name="Shopping Cart MCP Server (stdio)",
        tags=server_tags,
    )

    return mcp


async def main():
    """Main function to run stdio server."""
    mcp = create_stdio_mcp_server()

    # Use FastMCP's run_stdio_async method which is designed for async environments
    # This avoids the nested event loop issue with mcp.run()
    await mcp.run_stdio_async(show_banner=False)


if __name__ == "__main__":
    anyio.run(main)
