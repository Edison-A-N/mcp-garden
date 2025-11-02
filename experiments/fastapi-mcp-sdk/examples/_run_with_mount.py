"""
Shopping Cart MCP Server - Method 2: Using FastAPIMCPServer Mount
This example demonstrates how to create an MCP server using the mount approach.
This approach integrates the MCP server directly into the FastAPI app.
"""

import anyio
import os
import uvicorn

from fastapi_mcp_sdk import FastAPIMCPServer


async def create_mounted_mcp_server():
    """Create MCP server using mount approach."""
    # Import the configured app
    from _shopping_cart_app import app as shopping_cart_app

    # Enable experimental parser
    os.environ["FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER"] = "true"

    # Create MCP server
    mcp_server = FastAPIMCPServer()

    # Mount MCP server to FastAPI app
    app_with_mcp = mcp_server.mount_to_fastapi(
        app=shopping_cart_app,
        mount_path="/mcp",
        name="Shopping Cart MCP Server (Mounted)",
    )

    return app_with_mcp, mcp_server


async def main():
    """Main function to run the integrated server."""
    # Create integrated app
    app_with_mcp, mcp_server = await create_mounted_mcp_server()

    print("Server running:")
    print("  FastAPI: http://127.0.0.1:8000/docs")
    print("  MCP: http://127.0.0.1:8000/mcp")
    print("Press Ctrl+C to stop")

    # Run the integrated server
    config = uvicorn.Config(app=app_with_mcp, host="127.0.0.1", port=8000, log_level="info", reload=False)
    server = uvicorn.Server(config)

    try:
        await server.serve()
    except KeyboardInterrupt:
        if hasattr(mcp_server, "close"):
            await mcp_server.close()


if __name__ == "__main__":
    anyio.run(main)
