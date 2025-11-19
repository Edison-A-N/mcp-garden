"""MCP transport connection handlers"""

import logging
from typing import Dict, Any, Tuple
from mcp import ClientSession

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client

from mcp2code.config import MCPServerConfig

logger = logging.getLogger(__name__)


async def create_transport(
    server_config: MCPServerConfig,
) -> Tuple[Any, Any, Any]:
    """
    Create transport based on server configuration.

    Args:
        server_config: MCP server configuration

    Returns:
        Tuple of (transport, read, write) streams

    Raises:
        ValueError: If transport type is unsupported
        ImportError: If required transport client is not available
    """
    transport_type = server_config.get_transport_type()

    if transport_type == "stdio":
        return await _create_stdio_transport(server_config)
    elif transport_type == "sse":
        return await _create_sse_transport(server_config)
    elif transport_type == "http" or transport_type == "streamable-http":
        return await _create_http_transport(server_config)
    else:
        raise ValueError(f"Unsupported transport type: {transport_type}")


async def _create_stdio_transport(
    server_config: MCPServerConfig,
) -> Tuple[Any, Any, Any]:
    """Create stdio transport"""
    if not server_config.command:
        raise ValueError("Command required for stdio transport")

    server_params = StdioServerParameters(
        command=server_config.command,
        args=server_config.args,
        env=server_config.env,
    )

    transport = stdio_client(server_params)
    read, write = await transport.__aenter__()
    return transport, read, write


async def _create_sse_transport(
    server_config: MCPServerConfig,
) -> Tuple[Any, Any, Any]:
    """Create SSE transport"""
    if not server_config.url:
        raise ValueError("URL required for SSE transport")

    transport = sse_client(url=server_config.url, headers=server_config.headers)
    read, write = await transport.__aenter__()
    return transport, read, write


async def _create_http_transport(
    server_config: MCPServerConfig,
) -> Tuple[Any, Any, Any]:
    """Create HTTP transport"""
    if not server_config.url:
        raise ValueError("URL required for HTTP transport")
    if streamablehttp_client is None:
        raise ImportError("HTTP client not available. Install mcp with HTTP support.")

    transport = streamablehttp_client(
        url=server_config.url,
        headers=server_config.headers,
    )
    read, write, _ = await transport.__aenter__()
    return transport, read, write


async def discover_tools_from_server(
    server_name: str, server_config: MCPServerConfig
) -> list[Dict[str, Any]]:
    """
    Discover tools from a single MCP server.

    Args:
        server_name: Name of the server
        server_config: Server configuration

    Returns:
        List of discovered tools with their schemas
    """
    transport, read, write = await create_transport(server_config)

    try:
        tools = []
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            for tool in tools_result.tools:
                # Get input schema
                input_schema = (
                    tool.inputSchema.model_dump()
                    if hasattr(tool.inputSchema, "model_dump")
                    else tool.inputSchema
                )

                # Get output schema if available
                # MCP SDK may not include outputSchema in Tool definition
                # Check multiple possible attribute names
                output_schema = None
                if hasattr(tool, "outputSchema") and tool.outputSchema:
                    output_schema = (
                        tool.outputSchema.model_dump()
                        if hasattr(tool.outputSchema, "model_dump")
                        else tool.outputSchema
                    )
                elif hasattr(tool, "output_schema") and tool.output_schema:
                    output_schema = (
                        tool.output_schema.model_dump()
                        if hasattr(tool.output_schema, "model_dump")
                        else tool.output_schema
                    )
                # Also check if it's in the dict representation
                elif isinstance(tool, dict) and "outputSchema" in tool:
                    output_schema = tool["outputSchema"]
                elif isinstance(tool, dict) and "output_schema" in tool:
                    output_schema = tool["output_schema"]
                # Debug: log available attributes if outputSchema not found
                elif logger.isEnabledFor(logging.DEBUG):
                    attrs = [attr for attr in dir(tool) if not attr.startswith("_")]
                    logger.debug(f"Tool '{tool.name}' attributes: {attrs}")

                tools.append(
                    {
                        "name": tool.name,
                        "description": tool.description or "",
                        "inputSchema": input_schema,
                        "outputSchema": output_schema,
                    }
                )
        return tools
    finally:
        # Close transport
        await transport.__aexit__(None, None, None)
