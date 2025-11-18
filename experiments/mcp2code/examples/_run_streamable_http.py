"""
Shopping Cart MCP Server - streamable_http transport
This script runs the shopping cart MCP server using streamable_http transport.
It starts a FastAPI server with MCP mounted at /mcp endpoint.
"""

import os
import sys
import uvicorn
from pathlib import Path

# Enable experimental parser BEFORE importing FastMCP
os.environ["FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER"] = "true"
# Disable FastMCP banner/logo
os.environ["FASTMCP_SHOW_CLI_BANNER"] = "false"

import anyio
from contextlib import asynccontextmanager
from fastmcp import FastMCP
from fastapi import FastAPI

# Add current directory to path to import shopping cart app
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))


async def create_streamable_http_server():
    """Create MCP server using streamable_http transport."""
    # Import the configured app
    from _shopping_cart_app import app as shopping_cart_app

    # Define tags for the MCP server
    server_tags = {"shopping", "ecommerce", "cart", "orders", "products", "users"}

    # Create MCP server from FastAPI app
    mcp = FastMCP.from_fastapi(
        app=shopping_cart_app,
        name="Shopping Cart MCP Server (streamable_http)",
        tags=server_tags,
    )

    # Create streamable_http ASGI app
    # Path is set in http_app, so we don't need prefix in include_router
    mcp_app = mcp.http_app(
        path="/mcp",
        transport="streamable-http",
        json_response=False,
        stateless_http=True,
    )

    # Get original lifespan from FastAPI app
    original_lifespan = getattr(shopping_cart_app.router, "lifespan_context", None)

    # Create combined lifespan that includes both FastAPI and MCP lifespans
    @asynccontextmanager
    async def combined_lifespan(app: FastAPI):
        # Start both lifespans
        if original_lifespan:
            async with original_lifespan(app):
                if hasattr(mcp_app, "lifespan"):
                    async with mcp_app.lifespan(app):
                        yield
                else:
                    yield
        else:
            if hasattr(mcp_app, "lifespan"):
                async with mcp_app.lifespan(app):
                    yield
            else:
                yield

    # Set the combined lifespan to FastAPI app
    shopping_cart_app.router.lifespan_context = combined_lifespan

    # Include MCP routes in FastAPI app using include_router
    # This is the correct way to integrate FastMCP with FastAPI
    # Path is already set in http_app, so no prefix needed
    from fastapi import APIRouter

    mcp_router = APIRouter(
        tags=["mcp"],
        routes=mcp_app.routes,
    )
    shopping_cart_app.include_router(mcp_router)

    return shopping_cart_app, mcp


async def main():
    """Main function to run the streamable_http server."""
    # Create integrated app
    app_with_mcp, mcp = await create_streamable_http_server()

    print("Server running:")
    print("  FastAPI: http://127.0.0.1:8000/docs")
    print("  MCP: http://127.0.0.1:8000/mcp")
    print("Press Ctrl+C to stop")

    # Run the integrated server
    config = uvicorn.Config(
        app=app_with_mcp,
        host="127.0.0.1",
        port=8000,
        log_level="info",
        reload=False,
    )
    server = uvicorn.Server(config)

    try:
        await server.serve()
    except KeyboardInterrupt:
        if hasattr(mcp, "close"):
            await mcp.close()


if __name__ == "__main__":
    anyio.run(main)
