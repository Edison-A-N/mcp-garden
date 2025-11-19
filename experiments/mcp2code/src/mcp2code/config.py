"""MCP configuration parser"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    """MCP server configuration"""

    # For stdio transport
    command: Optional[str] = None
    args: list[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)

    # For SSE/HTTP transport
    url: Optional[str] = None

    # Transport type (defaults to stdio if command is provided, otherwise SSE)
    transport: Optional[Literal["stdio", "sse", "streamable-http", "http"]] = None

    # Additional headers for SSE/HTTP
    headers: Dict[str, str] = Field(default_factory=dict)

    def get_transport_type(self) -> str:
        """Determine transport type from configuration"""
        if self.transport:
            return self.transport
        if self.url:
            return "streamable-http"  # Default to streamable_http for URL-based connections
        if self.command:
            return "stdio"  # Default to stdio for command-based connections
        raise ValueError("Must specify either command (for stdio) or url (for streamable_http)")


class MCPConfig(BaseModel):
    """MCP configuration model"""

    mcpServers: Dict[str, MCPServerConfig] = Field(default_factory=dict)

    @classmethod
    def from_file(cls, config_path: str) -> "MCPConfig":
        """Load MCP config from file"""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"MCP config file not found: {config_path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls(**data)

    @classmethod
    def from_json(cls, json_data: str) -> "MCPConfig":
        """Create MCP config from JSON string"""
        data = json.loads(json_data)
        return cls(**data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPConfig":
        """Create MCP config from dictionary"""
        return cls(**data)

    def get_server_config(self, server_name: str) -> Optional[MCPServerConfig]:
        """Get server configuration by name"""
        return self.mcpServers.get(server_name)
