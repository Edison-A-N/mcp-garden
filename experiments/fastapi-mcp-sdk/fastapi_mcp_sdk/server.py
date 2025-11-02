"""
FastAPI MCP Server implementation using mount approach.
This module provides a way to mount FastMCP servers directly into FastAPI applications.
"""

import os
import logging
from typing import Optional
from contextlib import asynccontextmanager

import httpx
from fastmcp import FastMCP
from fastapi import FastAPI, APIRouter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FastAPIMCPServer:
    """
    A server that mounts FastMCP servers directly into FastAPI applications.
    This approach avoids HTTP client overhead by integrating MCP functionality
    directly into the FastAPI application.
    """

    def __init__(self, enable_experimental_parser: bool = True):
        """
        Initialize the FastAPI MCP Server.

        Args:
            enable_experimental_parser: Whether to enable FastMCP experimental parser.
        """
        self.mcp_server: Optional[FastMCP] = None
        self.client: Optional[httpx.AsyncClient] = None

        # Enable experimental parser if configured
        if enable_experimental_parser:
            os.environ["FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER"] = "true"

    def _create_mcp_server(self, app: FastAPI, name: Optional[str] = None) -> FastMCP:
        """
        Create MCP server from FastAPI app's OpenAPI spec.

        Creates an httpx.AsyncClient with ASGITransport to call endpoints via FastAPI's ASGI interface.
        """
        logger.info("Creating MCP server...")

        # Get OpenAPI spec from the FastAPI app
        logger.info("Getting OpenAPI spec from FastAPI app")
        openapi_spec = app.openapi()
        logger.info(f"OpenAPI spec keys: {list(openapi_spec.keys())}")

        # Create MCP server from OpenAPI spec
        server_name = name or f"{app.title or 'FastAPI'} MCP Server"
        logger.info(f"Creating MCP server with name: {server_name}")
        logger.info(f"OpenAPI spec has {len(openapi_spec.get('paths', {}))} paths")

        try:
            # Create httpx client with ASGITransport to call FastAPI app directly via ASGI
            self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fastapi.io")
            logger.info("Created httpx.AsyncClient with ASGITransport for direct ASGI calls")

            mcp_server = FastMCP.from_openapi(
                openapi_spec=openapi_spec,
                client=self.client,
                name=server_name,
            )
            logger.info("MCP server created successfully")
            return mcp_server
        except Exception as e:
            logger.error(f"Failed to create MCP server: {str(e)}", exc_info=True)
            raise

    def mount_to_fastapi(
        self,
        app: FastAPI,
        mount_path: Optional[str] = None,
        name: Optional[str] = None,
    ) -> FastAPI:
        """
        Mount the MCP server directly to a FastAPI application using FastAPI's mount method.
        This approach avoids HTTP client overhead by integrating MCP functionality
        directly into the FastAPI application.

        Args:
            app: The FastAPI application to mount to
            mount_path: Path to mount the MCP server at. If None, uses "/mcp" as default.
            name: Name for the MCP server.

        Returns:
            The FastAPI app with MCP server mounted

        Example:
            ```python
            mcp_server.mount_to_fastapi(
                app=app,
                mount_path="/mcp",
            )
            ```
        """
        if mount_path:
            mount_path = mount_path.rstrip("/")
        else:
            mount_path = "/mcp"  # default mount path

        # Create MCP server immediately
        self.mcp_server = self._create_mcp_server(app, name)

        # Get the ASGI app from FastMCP server
        logger.info(f"Getting ASGI app from FastMCP server at path: {mount_path}")
        try:
            mcp_starlette_app = self.mcp_server.http_app(path=mount_path)
            logger.info("Successfully got ASGI app from FastMCP server")

            # Check the routes in the MCP app
            if hasattr(mcp_starlette_app, "routes"):
                logger.info(f"MCP app routes: {[route.path for route in mcp_starlette_app.routes]}")

        except Exception as e:
            logger.error(f"Failed to get ASGI app from FastMCP server: {str(e)}", exc_info=True)
            raise

        # Use the Starlette app directly
        mcp_asgi_app = mcp_starlette_app

        # Store the original lifespan if it exists
        original_lifespan = getattr(app, "router", {}).lifespan_context if hasattr(app, "router") else None

        # Create a new lifespan that combines MCP server lifecycle with any existing lifespan
        @asynccontextmanager
        async def combined_lifespan(app: FastAPI):
            # Startup - MCP server is already created and mounted
            logger.info("MCP server lifespan started")

            # If there's an existing lifespan, run it too
            if original_lifespan:
                async with original_lifespan(app):
                    # Check if mcp_asgi_app has lifespan
                    if mcp_asgi_app and hasattr(mcp_asgi_app, "lifespan"):
                        async with mcp_asgi_app.lifespan(app):
                            yield
                    else:
                        yield
            else:
                # Check if mcp_asgi_app has lifespan
                if mcp_asgi_app and hasattr(mcp_asgi_app, "lifespan"):
                    async with mcp_asgi_app.lifespan(app):
                        yield
                else:
                    yield

            # Shutdown
            logger.info("Shutting down MCP server...")
            try:
                await self.close()
                logger.info("MCP server shutdown complete")
            except Exception as e:
                logger.error(f"Error during MCP server shutdown: {str(e)}", exc_info=True)

        # Set the combined lifespan
        app.router.lifespan_context = combined_lifespan

        # Mount the MCP ASGI app
        mcp_routes = mcp_asgi_app.routes
        mcp_router = APIRouter(
            tags=["mcp"],
            routes=mcp_routes,
        )

        app.include_router(mcp_router)

        return app

    async def close(self):
        """Close any resources."""
        if self.client is not None:
            await self.client.aclose()
            self.client = None
        if hasattr(self.mcp_server, "close"):
            await self.mcp_server.close()
