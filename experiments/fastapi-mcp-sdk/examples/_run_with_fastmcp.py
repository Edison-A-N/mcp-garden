"""
Shopping Cart MCP Server - Method 1: Using FastMCP.from_fastapi
This example demonstrates how to create an MCP server using FastMCP.from_fastapi method.
This approach creates a separate MCP server that connects to the FastAPI app via HTTP.
"""

import anyio
import os
import uvicorn

from fastmcp import FastMCP


async def create_fastmcp_server():
    """Create MCP server using FastMCP.from_fastapi method."""
    # Import the configured app
    from _shopping_cart_app import app as shopping_cart_app

    # Enable experimental parser
    os.environ["FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER"] = "true"

    # Define tags for the MCP server
    server_tags = {"shopping", "ecommerce", "cart", "orders", "products", "users"}

    # Create MCP server from FastAPI app
    mcp = FastMCP.from_fastapi(
        app=shopping_cart_app,
        name="Shopping Cart MCP Server",
        tags=server_tags,
    )

    # Create HTTP ASGI app
    mcp_app = mcp.http_app(
        path="/mcp",
        transport="streamable-http",
        json_response=True,
        stateless_http=True,
    )

    return mcp_app


async def run_fastapi_server():
    """Run the FastAPI server on port 8000."""
    # Import the configured app
    from _shopping_cart_app import app as shopping_cart_app

    config = uvicorn.Config(
        app=shopping_cart_app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
        reload=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run_mcp_server():
    """Run the MCP server on port 8001."""
    mcp_app = await create_fastmcp_server()
    config = uvicorn.Config(app=mcp_app, host="127.0.0.1", port=8001, log_level="info", reload=False)
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """Main function to run both servers."""
    # Use anyio task group to manage concurrent tasks
    async with anyio.create_task_group() as tg:
        # Start FastAPI server in background
        tg.start_soon(run_fastapi_server)

        # Wait a moment for FastAPI to start
        await anyio.sleep(2)

        # Start MCP server in background
        tg.start_soon(run_mcp_server)

        print("Servers running:")
        print("  FastAPI: http://127.0.0.1:8000/docs")
        print("  MCP: http://127.0.0.1:8001/mcp")
        print("Press Ctrl+C to stop")


if __name__ == "__main__":
    anyio.run(main)
