"""
FastAPI MCP SDK - A streamlined SDK for converting FastAPI applications to MCP servers.

This package provides utilities to convert FastAPI applications into MCP (Model Context Protocol) servers
using FastMCP's experimental OpenAPI parser.
"""

from .server import FastAPIMCPServer

__version__ = "0.1.0"
__all__ = ["FastAPIMCPServer"]
