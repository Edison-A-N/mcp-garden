"""
FastAPI MCP Server implementation using mount approach.
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
    """Mounts FastMCP servers directly into FastAPI applications."""

    def __init__(self, enable_experimental_parser: bool = True):
        """
        Args:
            enable_experimental_parser: Whether to enable FastMCP experimental parser.
        """
        self.mcp_server: Optional[FastMCP] = None
        self.client: Optional[httpx.AsyncClient] = None

        if enable_experimental_parser:
            os.environ["FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER"] = "true"

    def _create_mcp_server(self, app: FastAPI, name: Optional[str] = None) -> FastMCP:
        """Create MCP server from FastAPI app's OpenAPI spec."""
        logger.info("Creating MCP server...")
        openapi_spec = app.openapi()
        logger.info(f"OpenAPI spec keys: {list(openapi_spec.keys())}")

        server_name = name or f"{app.title or 'FastAPI'} MCP Server"
        logger.info(f"Creating MCP server with name: {server_name}")
        logger.info(f"OpenAPI spec has {len(openapi_spec.get('paths', {}))} paths")

        try:
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
        Mount the MCP server directly to a FastAPI application.

        Args:
            app: The FastAPI application to mount to
            mount_path: Path to mount the MCP server at. Defaults to "/mcp".
            name: Name for the MCP server.

        Returns:
            The FastAPI app with MCP server mounted
        """
        if mount_path:
            mount_path = mount_path.rstrip("/")
        else:
            mount_path = "/mcp"

        self.mcp_server = self._create_mcp_server(app, name)

        logger.info(f"Getting ASGI app from FastMCP server at path: {mount_path}")
        try:
            mcp_starlette_app = self.mcp_server.http_app(path=mount_path)
            logger.info("Successfully got ASGI app from FastMCP server")

            if hasattr(mcp_starlette_app, "routes"):
                logger.info(f"MCP app routes: {[route.path for route in mcp_starlette_app.routes]}")

        except Exception as e:
            logger.error(f"Failed to get ASGI app from FastMCP server: {str(e)}", exc_info=True)
            raise

        mcp_asgi_app = mcp_starlette_app
        original_lifespan = getattr(app, "router", {}).lifespan_context if hasattr(app, "router") else None

        @asynccontextmanager
        async def combined_lifespan(app: FastAPI):
            logger.info("MCP server lifespan started")

            if original_lifespan:
                async with original_lifespan(app):
                    if mcp_asgi_app and hasattr(mcp_asgi_app, "lifespan"):
                        async with mcp_asgi_app.lifespan(app):
                            yield
                    else:
                        yield
            else:
                if mcp_asgi_app and hasattr(mcp_asgi_app, "lifespan"):
                    async with mcp_asgi_app.lifespan(app):
                        yield
                else:
                    yield

            logger.info("Shutting down MCP server...")
            try:
                await self.close()
                logger.info("MCP server shutdown complete")
            except Exception as e:
                logger.error(f"Error during MCP server shutdown: {str(e)}", exc_info=True)

        app.router.lifespan_context = combined_lifespan

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
